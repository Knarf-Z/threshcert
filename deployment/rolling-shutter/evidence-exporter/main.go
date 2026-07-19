package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/jackc/pgx/v4/pgxpool"
	"github.com/shutter-network/shutter/shlib/shcrypto"

	obsdb "github.com/shutter-network/rolling-shutter/rolling-shutter/chainobserver/db/keyper"
	coredb "github.com/shutter-network/rolling-shutter/rolling-shutter/keyper/database"
	servicedb "github.com/shutter-network/rolling-shutter/rolling-shutter/keyperimpl/shutterservice/database"
	"github.com/shutter-network/rolling-shutter/rolling-shutter/keyperimpl/shutterservice/serviceztypes"
	"github.com/shutter-network/rolling-shutter/rolling-shutter/medley/identitypreimage"
	"github.com/shutter-network/rolling-shutter/rolling-shutter/shdb"
)

const (
	schemaEvidence = "fc-shutter-evidence-v1"
	schemaKeypers  = "fc-keyper-set-v1"
	pinnedVersion  = "v1.4.4"
	pinnedCommit   = "d143fffcf51f85b30375134d2d29756417f333b9"
)

type keyperEntry struct {
	Index   int    `json:"index"`
	Address string `json:"address"`
}

type keyperSetOutput struct {
	Schema                string        `json:"schema"`
	GeneratedAt           string        `json:"generatedAt"`
	RollingShutterVersion string        `json:"rollingShutterVersion"`
	RollingShutterCommit  string        `json:"rollingShutterCommit"`
	KeyperConfigIndex     int64         `json:"keyperConfigIndex"`
	Threshold             int32         `json:"threshold"`
	Keypers               []keyperEntry `json:"keypers"`
}

type shareOutput struct {
	MemberIndex          int    `json:"memberIndex"`
	KeyperAddress        string `json:"keyperAddress"`
	Share                string `json:"share"`
	ShareHash            string `json:"shareHash"`
	PublicKeyShare       string `json:"publicKeyShare"`
	ShareValid           bool   `json:"shareValid"`
	NativeSignature      string `json:"nativeSignature"`
	NativeSignatureHash  string `json:"nativeSignatureHash"`
	NativeSignatureValid bool   `json:"nativeSignatureValid"`
}

type evidenceOutput struct {
	Schema                         string        `json:"schema"`
	GeneratedAt                    string        `json:"generatedAt"`
	RollingShutterVersion          string        `json:"rollingShutterVersion"`
	RollingShutterCommit           string        `json:"rollingShutterCommit"`
	InstanceID                     uint64        `json:"instanceId"`
	Eon                            string        `json:"eon"`
	EpochID                        string        `json:"epochId"`
	Threshold                      int32         `json:"threshold"`
	NumKeypers                     int           `json:"numKeypers"`
	IdentityPreimage               string        `json:"identityPreimage"`
	IdentityHash                   string        `json:"identityHash"`
	AggregateKey                   string        `json:"aggregateKey"`
	AggregateKeyValid              bool          `json:"aggregateKeyValid"`
	ReconstructionMatchesStoredKey bool          `json:"reconstructionMatchesStoredKey"`
	Shares                         []shareOutput `json:"shares"`
}

func hex0x(b []byte) string { return "0x" + hex.EncodeToString(b) }

func writeJSON(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if path == "-" {
		_, err = os.Stdout.Write(data)
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func decodePreimage(value string) (identitypreimage.IdentityPreimage, error) {
	value = strings.TrimPrefix(strings.TrimSpace(value), "0x")
	b, err := hex.DecodeString(value)
	if err != nil {
		return nil, fmt.Errorf("decode identity preimage: %w", err)
	}
	if len(b) != 32 {
		return nil, fmt.Errorf("identity preimage must be exactly 32 bytes, got %d", len(b))
	}
	return identitypreimage.IdentityPreimage(b), nil
}

func recordKeyperIndex(seen map[int64]struct{}, index int64, count int) error {
	if index < 0 || index >= int64(count) {
		return fmt.Errorf("out-of-range keyper index %d", index)
	}
	if _, exists := seen[index]; exists {
		return fmt.Errorf("duplicate keyper index %d", index)
	}
	seen[index] = struct{}{}
	return nil
}

func loadKeyperSet(ctx context.Context, pool *pgxpool.Pool, index int64) (obsdb.KeyperSet, []keyperEntry, error) {
	set, err := obsdb.New(pool).GetKeyperSetByKeyperConfigIndex(ctx, index)
	if err != nil {
		return obsdb.KeyperSet{}, nil, fmt.Errorf("load keyper set %d: %w", index, err)
	}
	entries := make([]keyperEntry, len(set.Keypers))
	for i, raw := range set.Keypers {
		address, err := shdb.DecodeAddress(raw)
		if err != nil {
			return obsdb.KeyperSet{}, nil, fmt.Errorf("decode keyper %d address: %w", i, err)
		}
		entries[i] = keyperEntry{Index: i, Address: address.Hex()}
	}
	return set, entries, nil
}

func run() error {
	var (
		databaseURL = flag.String("database-url", "", "PostgreSQL URL for one Shutter service Keyper")
		configIndex = flag.Int64("keyper-config-index", 0, "Shutter keyper-config index (protocol eon)")
		instanceID  = flag.Uint64("instance-id", 0, "Shutter service instance ID")
		preimageHex = flag.String("identity-preimage", "", "32-byte 0x-prefixed identity preimage")
		outputPath  = flag.String("output", "-", "output JSON path, or - for stdout")
		keypersOnly = flag.Bool("keyper-set-only", false, "export only the bonded Keyper address set")
		requireAll  = flag.Bool("require-all", true, "require valid shares and signatures from all seven Keypers")
	)
	flag.Parse()
	if *databaseURL == "" {
		return fmt.Errorf("--database-url is required")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	pool, err := pgxpool.Connect(ctx, *databaseURL)
	if err != nil {
		return fmt.Errorf("connect database: %w", err)
	}
	defer pool.Close()

	set, entries, err := loadKeyperSet(ctx, pool, *configIndex)
	if err != nil {
		return err
	}
	if len(entries) != 7 || set.Threshold != 4 {
		return fmt.Errorf("refusing non-pilot keyper set: got %d-of-%d, require 4-of-7", set.Threshold, len(entries))
	}
	if *keypersOnly {
		return writeJSON(*outputPath, keyperSetOutput{
			Schema: schemaKeypers, GeneratedAt: time.Now().UTC().Format(time.RFC3339Nano),
			RollingShutterVersion: pinnedVersion, RollingShutterCommit: pinnedCommit,
			KeyperConfigIndex: *configIndex, Threshold: set.Threshold, Keypers: entries,
		})
	}

	preimage, err := decodePreimage(*preimageHex)
	if err != nil {
		return err
	}
	epochID := shcrypto.ComputeEpochID(preimage.Bytes())
	identityHash := crypto.Keccak256(preimage.Bytes())

	core := coredb.New(pool)
	dkgRow, err := core.GetDKGResultForKeyperConfigIndex(ctx, *configIndex)
	if err != nil {
		return fmt.Errorf("load DKG result: %w", err)
	}
	if !dkgRow.Success {
		return fmt.Errorf("DKG result for keyper set %d is not successful", *configIndex)
	}
	dkg, err := shdb.DecodePureDKGResult(dkgRow.PureResult)
	if err != nil {
		return fmt.Errorf("decode DKG result: %w", err)
	}
	if int(dkg.NumKeypers) != len(entries) || int32(dkg.Threshold) != set.Threshold {
		return fmt.Errorf("DKG dimensions do not match the observed keyper set")
	}

	shareRows, err := core.SelectDecryptionKeyShares(ctx, coredb.SelectDecryptionKeySharesParams{
		Eon: *configIndex, EpochID: preimage.Bytes(),
	})
	if err != nil {
		return fmt.Errorf("load decryption key shares: %w", err)
	}
	sort.Slice(shareRows, func(i, j int) bool { return shareRows[i].KeyperIndex < shareRows[j].KeyperIndex })

	signatureRows, err := servicedb.New(pool).GetDecryptionSignatures(ctx, servicedb.GetDecryptionSignaturesParams{
		Eon: *configIndex, IdentitiesHash: identityHash, Limit: int32(len(entries)),
	})
	if err != nil {
		return fmt.Errorf("load native decryption signatures: %w", err)
	}
	signatures := make(map[int64][]byte, len(signatureRows))
	seenSignatureIndices := make(map[int64]struct{}, len(signatureRows))
	for _, row := range signatureRows {
		if err := recordKeyperIndex(seenSignatureIndices, row.KeyperIndex, len(entries)); err != nil {
			return fmt.Errorf("native signature row: %w", err)
		}
		signatures[row.KeyperIndex] = row.Signature
	}
	signatureData, err := serviceztypes.NewDecryptionSignatureData(*instanceID, uint64(*configIndex), []identitypreimage.IdentityPreimage{preimage})
	if err != nil {
		return fmt.Errorf("construct native signature payload: %w", err)
	}

	outputs := make([]shareOutput, 0, len(shareRows))
	validIndices := make([]int, 0, int(set.Threshold))
	validShares := make([]*shcrypto.EpochSecretKeyShare, 0, int(set.Threshold))
	seenShareIndices := make(map[int64]struct{}, len(shareRows))
	for _, row := range shareRows {
		if err := recordKeyperIndex(seenShareIndices, row.KeyperIndex, len(entries)); err != nil {
			return fmt.Errorf("decryption-share row: %w", err)
		}
		share, decodeErr := shdb.DecodeEpochSecretKeyShare(row.DecryptionKeyShare)
		shareValid := decodeErr == nil && shcrypto.VerifyEpochSecretKeyShare(
			share, dkg.PublicKeyShares[row.KeyperIndex], epochID,
		)
		signature := signatures[row.KeyperIndex]
		keyperAddress := common.HexToAddress(entries[row.KeyperIndex].Address)
		signatureValid := false
		if len(signature) > 0 {
			signatureValid, err = signatureData.CheckSignature(signature, keyperAddress)
			if err != nil {
				return fmt.Errorf("check native signature for keyper %d: %w", row.KeyperIndex, err)
			}
		}
		publicKeyShare := dkg.PublicKeyShares[row.KeyperIndex].Marshal()
		outputs = append(outputs, shareOutput{
			MemberIndex: int(row.KeyperIndex), KeyperAddress: keyperAddress.Hex(),
			Share: hex0x(row.DecryptionKeyShare), ShareHash: crypto.Keccak256Hash(row.DecryptionKeyShare).Hex(),
			PublicKeyShare: hex0x(publicKeyShare), ShareValid: shareValid,
			NativeSignature: hex0x(signature), NativeSignatureHash: crypto.Keccak256Hash(signature).Hex(),
			NativeSignatureValid: signatureValid,
		})
		if shareValid && signatureValid && len(validShares) < int(set.Threshold) {
			validIndices = append(validIndices, int(row.KeyperIndex))
			validShares = append(validShares, share)
		}
	}
	if *requireAll {
		if len(outputs) != len(entries) {
			return fmt.Errorf("expected all %d shares, found %d", len(entries), len(outputs))
		}
		for _, share := range outputs {
			if !share.ShareValid || !share.NativeSignatureValid {
				return fmt.Errorf("keyper %d lacks a valid share or native signature", share.MemberIndex)
			}
		}
	}
	if len(validShares) < int(set.Threshold) {
		return fmt.Errorf("only %d jointly valid shares; threshold is %d", len(validShares), set.Threshold)
	}

	reconstructed, err := shcrypto.ComputeEpochSecretKey(validIndices, validShares, uint64(set.Threshold))
	if err != nil {
		return fmt.Errorf("reconstruct aggregate key: %w", err)
	}
	storedRow, err := core.GetDecryptionKey(ctx, coredb.GetDecryptionKeyParams{
		Eon: *configIndex, EpochID: preimage.Bytes(),
	})
	if err != nil {
		return fmt.Errorf("load stored aggregate key: %w", err)
	}
	stored := new(shcrypto.EpochSecretKey)
	if err := stored.Unmarshal(storedRow.DecryptionKey); err != nil {
		return fmt.Errorf("decode stored aggregate key: %w", err)
	}
	aggregateValid, err := shcrypto.VerifyEpochSecretKey(stored, dkg.PublicKey, preimage.Bytes())
	if err != nil {
		return fmt.Errorf("verify aggregate key: %w", err)
	}
	matches := reconstructed.Equal(stored)
	if !aggregateValid || !matches {
		return fmt.Errorf("aggregate key validation failed (valid=%t reconstructed-match=%t)", aggregateValid, matches)
	}

	return writeJSON(*outputPath, evidenceOutput{
		Schema: schemaEvidence, GeneratedAt: time.Now().UTC().Format(time.RFC3339Nano),
		RollingShutterVersion: pinnedVersion, RollingShutterCommit: pinnedCommit,
		InstanceID: *instanceID, Eon: fmt.Sprint(*configIndex), EpochID: hex0x(epochID.Marshal()),
		Threshold: set.Threshold, NumKeypers: len(entries),
		IdentityPreimage: preimage.Hex(), IdentityHash: crypto.Keccak256Hash(preimage.Bytes()).Hex(),
		AggregateKey: hex0x(storedRow.DecryptionKey), AggregateKeyValid: aggregateValid,
		ReconstructionMatchesStoredKey: matches, Shares: outputs,
	})
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "evidence export failed:", err)
		os.Exit(1)
	}
}
