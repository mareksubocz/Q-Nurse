import dwavebinarycsp
# from instance_parser import Nurse, Shift
from operator import le, ge


class Shift:
    def __init__(self, nurseID, day):
        self.nurseID = nurseID
        self.day = day

    def __str__(self):
        return f"{nurseID}_{day}"


def get_label(nurseID, day, shift_type):
    return f"{nurseID}_{day}_{shift_type}"


def sum_to_one(*args):
    return sum(args) == 1


def sum_to_n(n, *args):
    return sum(args) == n


def get_bqm(shift_types={}, nurses={}, horizon=10, stitch_kwargs=None):

    csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.ISING)

    # one shift per person per day
    for nurse in nurses.keys():
        for day in range(horizon):
            labels = {get_label(nurse, day, st) for st in shift_types.keys()}
            csp.add_constraint(sum_to_one, labels)

    # no not_before violation
    allowed = {(0, 0), (1, 0), (0, 1)}
    for nurse in nurses.keys():
        for day in range(horizon - 1):
            for st_key, st_value in shift_types.items():
                for fst in st_value.not_before.keys():
                    csp.add_constraint(allowed,
                                       {get_label(nurse, day, st_key),
                                        get_label(nurse, day + 1, fst)})

    # no more than maxShifts
    for nurse in nurses:
        labels = set()
        for day in range(horizon):
            for st in shift_types.keys():
                labels.add(get_label(nurse, day, st))
        csp.add_constraint(
            lambda *args: le(nurse.maxShifts, sum(*args)), labels)

    # max consecutive shifts
    for nurse in nurses:
        labels = set()
        for day in range(horizon - (nurse.maxConsecutiveShifts + 1)):
            for i in range(nurse.maxConsecutiveShifts + 1):
                for st in shift_types.keys():
                    labels.add(get_label(nurse, day + 1, st))
        csp.add_constraint(
            lambda *args: ge(nurse.maxConsecutiveShifts, sum(*args)), labels)

    # min consecutive shifts
    for nurse in nurses:
        labels = set()
        for day in range(horizon - (nurse.minConsecutiveShifts + 1)):
            for i in range(nurse.minConsecutiveShifts + 1):
                for st in shift_types.keys():
                    labels.add(get_label(nurse, day + 1, st))
        csp.add_constraint(
            lambda *args: le(nurse.minConsecutiveShifts, sum(*args)), labels)

    stitch_kwargs = {}

    if stitch_kwargs is None:
        stitch_kwargs = {}
    bqm = dwavebinarycsp.stitch(csp, **stitch_kwargs)
    for nurse in nurses:
        for day in range(horizon):
            for st in shift_types.keys():
                label = get_label(nurse, day, st)
                bias = 1
                bqm.add_variable(label, bias)

    return bqm
