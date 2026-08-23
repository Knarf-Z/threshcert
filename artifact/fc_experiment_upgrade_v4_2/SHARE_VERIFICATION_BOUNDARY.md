# Share-verification boundary

The v4 contract experiment does not pretend that an ECDSA signature is a
threshold-decryption share. The two checks sit on opposite sides of an
explicit boundary:

1. a verifier process checks the native Rolling Shutter share against the
   DKG public-key share and epoch, checks the member's native signature, and
   checks threshold reconstruction;
2. after those checks pass, the verifier signs a typed attestation over the
   chain ID, verifier contract, escrow contract, offer ID, member address, and
   share hash;
3. `AttestedShareVerifier.sol` performs canonical ECDSA recovery and
   `AtomicBypassEscrow.sol` accepts the share only when that attestation is
   valid.

The reference implementation retained by the earlier real-certificate
artifact pinned Rolling Shutter `v1.4.4`, commit
`d143fffcf51f85b30375134d2d29756417f333b9`, and called
`shcrypto.VerifyEpochSecretKeyShare` before reconstruction. The compact
machine-readable description is in
`config/share_verifier.reference.json`.

## What the Solidity tests establish

- a correctly attested share is accepted;
- changing the share, member, offer, or escrow invalidates the proof;
- a signature from an untrusted attester is rejected;
- the escrow still requires an all-member package before settlement.

## What they do not establish

- the Solidity contract does not directly evaluate the Shutter pairing
  equation;
- the attester is a trust and availability assumption unless replaced by a
  quorum, a proof system, or a chain-native cryptographic verifier;
- passing tests does not show that production Keypers would accept a bypass
  offer;
- neither the contract nor its tests are a production security audit.
