import xml.etree.ElementTree as ET
import dwavebinarycsp
import os
from operator import le, ge
from datetime import date, datetime


def get_label(nurseID, day, shift_type):
    return f"{nurseID}_{day}_{shift_type}"


def sum_to_one(*args):
    return sum(args) == 1


def sum_to_n(n, *args):
    return sum(args) == n


def get_bqm(data, stitch_kwargs=None):

    csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.BINARY)

    start_date = datetime.strptime(
        str(data.find('StartDate').text), '%Y-%m-%d').date()
    end_date = datetime.strptime(
        str(data.find('EndDate').text), '%Y-%m-%d').date()
    num_of_days = (end_date - start_date).days + 1

    # one shift for same person per day
    for employee in data.find('Employees'):
        for day in range(num_of_days):
            labels = {get_label(employee.attrib['ID'], day, st.attrib['ID'])
                      for st in data.find('ShiftTypes')}
            csp.add_constraint(sum_to_one, labels)

    # no not_before violation
    # allowed = {(0, 0), (1, 0), (0, 1)}
    # for nurse in nurses.keys():
    #     for day in range(num_of_days):
    #         for st_key, st_value in shift_types.items():
    #             for fst in st_value.not_before:
    #                 csp.add_constraint(allowed,
    #                                    {get_label(nurse, day, st_key),
    #                                     get_label(nurse, day + 1, fst)})

    # no more than maxShifts
    # for nurse_key, nurse_value in nurses.items():
    #     labels = set()
    #     for st in shift_types.keys():
    #         for day in range(horizon):
    #             labels.add(get_label(nurse_key, day, st))
    #     csp.add_constraint(
    #         lambda *args: le(nurse_value.maxShifts[st], sum(args)), labels)

    # max consecutive shifts
    # for nurse_key, nurse_value in nurses.items():
    #     labels = set()
    #     for day in range(horizon - (nurse_value.maxConsecutiveShifts + 1)):
    #         for i in range(nurse_value.maxConsecutiveShifts + 1):
    #             for st in shift_types.keys():
    #                 labels.add(get_label(nurse_key, day + 1, st))
    #     csp.add_constraint(
    #         lambda *args: ge(nurse_value.maxConsecutiveShifts, sum(args)), labels)

    # min consecutive shifts
    # for nurse_key, nurse_value in nurses.items():
    #     labels = set()
    #     for day in range(horizon - (nurse_value.minConsecutiveShifts + 1)):
    #         for i in range(nurse_value.minConsecutiveShifts + 1):
    #             for st in shift_types.keys():
    #                 labels.add(get_label(nurse_key, day + 1, st))
    #     csp.add_constraint(
    #         lambda *args: le(nurse_value.minConsecutiveShifts, sum(args)), labels)

    if stitch_kwargs is None:
        stitch_kwargs = {}
    bqm = dwavebinarycsp.stitch(csp, **stitch_kwargs)
    pruned_variables = list(bqm.variables)
    print(pruned_variables)
    for employee in data.find('Employees'):
        for day in range(num_of_days):
            for st in data.find('ShiftTypes'):
                label = get_label(employee.attrib['ID'], day, st.attrib['ID'])
                bias = 1
                if label in pruned_variables:
                    bqm.add_variable(label, bias)

    return bqm


if __name__ == "__main__":
    file_name = "Instance1.ros"
    full_file = os.path.abspath(os.path.join('instances1_24', file_name))

    data = ET.parse(full_file)
    print(get_bqm(data))
    # root = data.getroot()
