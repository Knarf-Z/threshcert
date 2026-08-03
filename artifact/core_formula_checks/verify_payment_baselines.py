from fractions import Fraction


resistances = [1, 3, 6, 8, 11, 16, 25]
threshold = 4
expected = {
    "public-only": Fraction(0),
    "global-member-floor": Fraction(4),
    "exact-lower-tail": Fraction(18),
    "mean-heuristic": Fraction(40),
}
actual = {
    "public-only": Fraction(0),
    "global-member-floor": threshold * min(resistances),
    "exact-lower-tail": sum(sorted(resistances)[:threshold]),
    "mean-heuristic": threshold * Fraction(sum(resistances), len(resistances)),
}

for name, value in actual.items():
    if value != expected[name]:
        raise AssertionError(f"{name}: expected {expected[name]}, actual {value}")
    print(f"PAYMENT_BASELINE_{name.upper().replace('-', '_')}={value}")

print("PAYMENT_BASELINES=4_PASS")
