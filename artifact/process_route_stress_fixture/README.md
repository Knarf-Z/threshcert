# OPE-anchored process branch fixture (v2)

This reproducible process-language fixture upgrades v1 with explicit ordered Request, Transfer, Finalize, Respond, Deliver, and Return records. All contract and process quantities use the authenticated unit ope-unit-a. Gas, undeclared token transfers, undeclared coordinator fees, and off-chain transfers are outside this header.

Five fail-closed source cases provide reproducible candidate-bypass exclusions. Three successful process branches retain contract cost four while their net costs are four, three, and zero. The rebate and cross-session return branches are synthetic counterfactual overlays; they are not claims about observed deployment events.

Run:

    py -3.11 check_fixture_v2.py --verify
