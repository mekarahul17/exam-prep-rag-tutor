
import sympy as sp


def solve_quadratic(a, b, c) -> dict:
    """
    Solve ax² + bx + c = 0.

    Features:
    - Exact symbolic roots
    - Repeated-root detection
    - Complex-root support
    - Discriminant classification
    - Symbolic root verification
    """

    x = sp.symbols("x")

    a = sp.sympify(a)
    b = sp.sympify(b)
    c = sp.sympify(c)

    if a == 0:
        return {
            "success": False,
            "error": "The coefficient of x² must not be zero.",
        }

    equation = sp.expand(a * x**2 + b * x + c)

    # Calculate discriminant.
    discriminant = sp.simplify(b**2 - 4 * a * c)

    # Classify the nature of roots.
    if discriminant.is_positive:
        root_type = "Two distinct real roots"

    elif discriminant.is_zero:
        root_type = "Two equal real roots"

    elif discriminant.is_negative:
        root_type = "Two complex conjugate roots"

    else:
        root_type = "Roots require further symbolic evaluation"

    # Calculate roots and their multiplicities.
    root_data = sp.roots(equation, x)

    if sum(root_data.values()) != 2:
        return {
            "success": False,
            "error": "Unable to calculate both quadratic roots.",
        }

    verified_roots = []

    for root, multiplicity in root_data.items():

        substituted_value = sp.simplify(
            equation.subs(x, root)
        )

        verified = substituted_value == 0

        verified_roots.append({
            "root": str(root),
            "decimal": str(sp.N(root, 8)),
            "verified": bool(verified),
            "substitution_result": str(substituted_value),
            "multiplicity": int(multiplicity),
        })

    all_roots_verified = (
        len(verified_roots) > 0
        and all(
            item["verified"]
            for item in verified_roots
        )
        and sum(
            item["multiplicity"]
            for item in verified_roots
        ) == 2
    )

    return {
        "success": True,
        "equation": str(equation) + " = 0",
        "factorized_form": str(sp.factor(equation)),
        "coefficients": {
            "a": str(a),
            "b": str(b),
            "c": str(c),
        },
        "discriminant": str(discriminant),
        "root_type": root_type,
        "roots": verified_roots,
        "all_roots_verified": all_roots_verified,
    }
