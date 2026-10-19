"""Request-local scalar schedule isolation; never iterate unvalidated metadata."""
import math
from dataclasses import dataclass
from fractions import Fraction
from android_bridge.projected_drone_admission import AdmissionRejected


@dataclass(frozen=True)
class FrozenSchedule:
    quantity: object
    active: object = None
    inactive: object = None
    reload: object = None
    children: tuple = ()


def capture_schedule(root, horizon, check, reserve, *, module=True):
    """Capture ordinary EOS constructors once, then validate only frozen scalars.

    Bound uses outward-conservative binary64 advancement through H + maxStep,
    including the original first post-horizon stored cycle. No aggregate/average
    schedule property participates in admission.
    """
    from eos.utils.cycles import CycleInfo, CycleSequence
    def reject():
        raise AdmissionRejected('Remote repair schedule is outside the validated structural domain')
    def scalar(value):
        if type(value) not in (int, float): reject()
        if type(value) is int and value.bit_length() > 1023: reject()
        return value
    def capture(node, leaf_only=False):
        check(); reserve('schedule_node', 1)
        q = scalar(node.quantity)
        if math.isnan(q) or q <= 0 or (type(q) is int and q.bit_length() > 53): reject()
        if type(node) is CycleInfo:
            a, i, r = scalar(node.activeTime), scalar(node.inactiveTime), node.isInactivityReload
            if type(r) is not bool: reject()
            return FrozenSchedule(q, a, i, r)
        if type(node) is not CycleSequence or leaf_only or not module: reject()
        # Ordinary module constructor is exactly a two-leaf sequence. Reject
        # unsupported/unreachable structure before entering its generator.
        sequence = node.sequence
        if type(sequence) not in (list, tuple) or len(sequence) != 2: reject()
        reserve('schedule_children', 2)
        children = tuple(capture(child, True) for child in sequence)
        if children[0].quantity == math.inf: reject()
        return FrozenSchedule(q, children=children)
    if type(horizon) not in (int, float) or not math.isfinite(horizon) or horizon < 0:
        reject()
    frozen = capture(root)
    leaves = frozen.children or (frozen,)
    steps, actives = [], []
    reserve('schedule_validation_slots', len(leaves) * 2)
    for leaf in leaves:
        check()
        if not math.isfinite(leaf.active) or not math.isfinite(leaf.inactive) or leaf.active <= 0 or leaf.inactive < 0: reject()
        active, inactive = leaf.active / 1000, leaf.inactive / 1000
        step = active + inactive
        if not math.isfinite(step) or active <= 0: reject()
        actives.append(active); steps.append(step)
    extent = horizon + max(steps)
    if not math.isfinite(extent): reject()
    roundoff = math.ulp(math.nextafter(extent, math.inf))
    lower = math.nextafter(min(steps) - roundoff, 0.0)
    if lower <= 0 or min(actives) <= roundoff: reject()
    bound = int(Fraction(horizon) // Fraction(lower)) + 2
    def count(node):
        q = math.inf if node.quantity == math.inf else math.ceil(node.quantity)
        if not node.children: return q
        n = sum(count(child) for child in node.children)
        return math.inf if math.inf in (n, q) else n * q
    finite = count(frozen)
    if finite != math.inf: bound = min(bound, finite)
    reserve('cycle_bound', bound)
    reserve('traversal_bound', (bound + 1) * (2 * (1 + len(frozen.children)) + (2 if frozen.children else 1)))
    return frozen, bound


def reconstruct_schedule(frozen, check, reserve):
    """Original constructors/iterators, with no mutable module-owned references."""
    from eos.utils.cycles import CycleInfo, CycleSequence
    check(); reserve('schedule_clone', 1)
    if not frozen.children:
        return CycleInfo(frozen.active, frozen.inactive, frozen.quantity, frozen.reload)
    reserve('schedule_clone_children', len(frozen.children))
    return CycleSequence(tuple(reconstruct_schedule(c, check, reserve) for c in frozen.children), frozen.quantity)
