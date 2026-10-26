"""Glickman (2022), steps 2–8, including the revised Illinois solver."""

from dataclasses import dataclass
from math import exp, fsum, isfinite, log, pi, sqrt

SCALE = 173.7178
ALGORITHM = "glicko2-2022-v1"


@dataclass(frozen=True)
class Rating:
    rating: float = 1500.0
    rd: float = 350.0
    volatility: float = 0.06

    def __post_init__(self):
        if not all(isfinite(x) for x in (self.rating, self.rd, self.volatility)):
            raise ValueError("Rating parameters must be finite")
        if self.rd <= 0 or self.volatility <= 0:
            raise ValueError("RD and volatility must be positive")


def g(phi):
    return 1 / sqrt(1 + 3 * phi**2 / pi**2)


def expected(mu, opponent_mu, opponent_phi):
    x = g(opponent_phi) * (mu - opponent_mu)
    # Algebraically identical logistic, without exp overflow.
    return 1 / (1 + exp(-x)) if x >= 0 else exp(x) / (1 + exp(x))


def inactive(state, periods=1):
    if not isinstance(periods, int) or periods < 0:
        raise ValueError("Inactivity periods must be a nonnegative integer")
    return Rating(
        state.rating,
        SCALE * sqrt((state.rd / SCALE) ** 2 + periods * state.volatility**2),
        state.volatility,
    )


def update(state, results, *, tau=0.5, epsilon=1e-6, max_iterations=100):
    if not isfinite(tau) or tau <= 0 or not isfinite(epsilon) or epsilon <= 0:
        raise ValueError("tau and epsilon must be finite and positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    # Canonical ordering and fsum remove dependence on set input order.
    results = sorted(results, key=lambda r: (r[0].rating, r[0].rd, r[1]))
    if not results:
        return inactive(state)
    mu, phi = (state.rating - 1500) / SCALE, state.rd / SCALE
    terms = []
    for opponent, score in results:
        if score not in (0, 0.5, 1):
            raise ValueError("Score must be 0, 0.5 or 1")
        p = opponent.rd / SCALE
        e = expected(mu, (opponent.rating - 1500) / SCALE, p)
        terms.append((g(p), e, score))
    precision = fsum(weight**2 * e * (1 - e) for weight, e, _ in terms)
    if precision <= 0 or not isfinite(precision):
        raise ValueError("Results exceed floating point precision")
    variance = 1 / precision
    improvement = fsum(weight * (score - e) for weight, e, score in terms)
    delta = variance * improvement
    a = 2 * log(state.volatility)

    def f(x):
        ex = exp(x)
        return (
            ex * (delta**2 - phi**2 - variance - ex) / (2 * (phi**2 + variance + ex) ** 2)
            - (x - a) / tau**2
        )

    A = a
    if delta**2 > phi**2 + variance:
        B = log(delta**2 - phi**2 - variance)
    else:
        for k in range(1, max_iterations + 1):
            B = a - k * tau
            if f(B) >= 0:
                break
        else:
            raise ArithmeticError("Volatility bracketing did not converge")
    fA, fB = f(A), f(B)
    for _ in range(max_iterations):
        if abs(B - A) <= epsilon:
            break
        if fB == fA:
            raise ArithmeticError("Degenerate volatility bracket")
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA /= 2
        B, fB = C, fC
    else:
        raise ArithmeticError("Volatility solver did not converge")
    sigma = exp(A / 2)
    phi_star = sqrt(phi**2 + sigma**2)
    new_phi = 1 / sqrt(1 / phi_star**2 + 1 / variance)
    return Rating(1500 + SCALE * (mu + new_phi**2 * improvement), SCALE * new_phi, sigma)
