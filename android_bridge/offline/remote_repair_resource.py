"""G05.2a conservative request-local allocation admission.

These are calibrated nominal allocation units, NOT Android heap-byte estimates.
The monotonic ledger deliberately does not reclaim temporaries. Deadline checks
remain independently mandatory. Native runtime qualification is a separate gate.
"""
from android_bridge.projected_drone_admission import AdmissionRejected

MAX_COUNTER = 2**63 - 1
DEFAULT_ALLOWANCE = 96 * 1024 * 1024
PRICES = {
    'container': 128, 'mapping_slot': 320, 'copy_slot': 320,
    'list_slot': 64, 'rr_value': 448, 'segment': 128, 'sort_slot': 32,
    'output_point': 128, 'output_slot': 320,
    'schedule_node': 512, 'schedule_clone': 512, 'schedule_constructor': 512,
    'schedule_children': 64, 'schedule_clone_children': 64,
    'schedule_validation_slots': 320, 'cycle': 256,
    'repair_parameter_call': 256,
    'container_row': 0, 'cycle_bound': 0, 'traversal_bound': 0,
    'scan': 0, 'sort_work': 0, 'serialization_unit': 6,
    'source_column_row': 8192, 'source_column_call': 1024,
}


class RepairReservation:
    """One whole-request ledger, including all fits and retained scalar outputs."""
    def __init__(self, allowance=DEFAULT_ALLOWANCE):
        if type(allowance) is not int or not 0 <= allowance <= MAX_COUNTER:
            raise AdmissionRejected('Invalid remote repair resource allowance')
        self.allowance = allowance
        self.used = 0
        self.count = 0

    def __call__(self, kind, count):
        if kind not in PRICES or type(count) is not int or count < 0 or count > MAX_COUNTER - self.count:
            raise AdmissionRejected('Invalid remote repair resource reservation')
        price = PRICES[kind]
        if price and count > (MAX_COUNTER - self.used) // price:
            raise AdmissionRejected('Remote repair resource accounting overflow')
        cost = count * price
        if cost > self.allowance - self.used:
            raise AdmissionRejected('Remote repair request exceeds the allocation allowance; no partial graph was returned')
        self.count += count
        self.used += cost
