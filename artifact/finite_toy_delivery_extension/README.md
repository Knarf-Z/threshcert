# Finite process delivery extension (v15)

This formal-sanity fixture replaces the ambiguous "second submit means success" interpretation with an explicit finite action language. The first-success traces contain separate open, finalize, two member submissions, and deliver actions. Members are M_1 and M_2; A and S are reserved for the attacker and service-side roles.

Run:

    py -3.11 check_toy_v15.py --verify

The checker enumerates the full finite LTS, replays both first-success routes, checks P1-P5 in the declared language, and rejects missing-delivery, pre-finality-delivery, undeclared-bypass, and role-alias mutations. It is a formal sanity instance, not production evidence.
