package main

import (
	"bytes"
	"crypto/rand"
	"testing"

	"github.com/ethereum/go-ethereum/crypto"
	"github.com/shutter-network/shutter/shlib/shcrypto"

	"github.com/shutter-network/rolling-shutter/rolling-shutter/keyperimpl/shutterservice/serviceztypes"
	"github.com/shutter-network/rolling-shutter/rolling-shutter/medley/identitypreimage"
	"github.com/shutter-network/rolling-shutter/rolling-shutter/medley/testkeygen"
)

func TestFourOfSevenShareValidationAndReconstruction(t *testing.T) {
	keys, err := testkeygen.NewEonKeys(rand.Reader, 7, 4)
	if err != nil {
		t.Fatal(err)
	}
	preimage := identitypreimage.IdentityPreimage(bytes.Repeat([]byte{0x42}, 32))
	epochID := shcrypto.ComputeEpochID(preimage.Bytes())
	indices := []int{0, 1, 2, 3}
	shares := make([]*shcrypto.EpochSecretKeyShare, 0, 4)
	for index := 0; index < 7; index++ {
		share := keys.EpochSecretKeyShare(preimage, index)
		if !shcrypto.VerifyEpochSecretKeyShare(share, keys.EonPublicKeyShare(index), epochID) {
			t.Fatalf("share %d failed validation", index)
		}
		if index < 4 {
			shares = append(shares, share)
		}
	}
	reconstructed, err := shcrypto.ComputeEpochSecretKey(indices, shares, 4)
	if err != nil {
		t.Fatal(err)
	}
	expected, err := keys.EpochSecretKey(preimage)
	if err != nil {
		t.Fatal(err)
	}
	if !reconstructed.Equal(expected) {
		t.Fatal("four-share reconstruction did not match expected aggregate")
	}
}

func TestNativeKeyperSignatureBindsInstanceEonAndIdentity(t *testing.T) {
	key, err := crypto.GenerateKey()
	if err != nil {
		t.Fatal(err)
	}
	preimage := identitypreimage.IdentityPreimage(bytes.Repeat([]byte{0x7a}, 32))
	data, err := serviceztypes.NewDecryptionSignatureData(0, 1, []identitypreimage.IdentityPreimage{preimage})
	if err != nil {
		t.Fatal(err)
	}
	signature, err := data.ComputeSignature(key)
	if err != nil {
		t.Fatal(err)
	}
	valid, err := data.CheckSignature(signature, crypto.PubkeyToAddress(key.PublicKey))
	if err != nil || !valid {
		t.Fatalf("native signature rejected: valid=%t err=%v", valid, err)
	}
	wrong, err := serviceztypes.NewDecryptionSignatureData(0, 2, []identitypreimage.IdentityPreimage{preimage})
	if err != nil {
		t.Fatal(err)
	}
	valid, err = wrong.CheckSignature(signature, crypto.PubkeyToAddress(key.PublicKey))
	if err != nil {
		t.Fatal(err)
	}
	if valid {
		t.Fatal("signature remained valid after changing the eon")
	}
}

func TestIdentityPreimageLengthGate(t *testing.T) {
	if _, err := decodePreimage("0x1234"); err == nil {
		t.Fatal("short identity preimage was accepted")
	}
	if _, err := decodePreimage("0x" + string(bytes.Repeat([]byte{'a'}, 64))); err != nil {
		t.Fatalf("32-byte identity preimage was rejected: %v", err)
	}
}
