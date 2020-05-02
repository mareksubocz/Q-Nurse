import xml.etree.ElementTree as ET
import os
from operator import le, ge
from datetime import date, datetime
from itertools import product

import neal
import dwavebinarycsp
from dwave.system.composites import EmbeddingComposite
from dwave.system.samplers import DWaveSampler

from pprint import pprint


def get_label(nurseID, day, shift_type):
    return f"{nurseID}_{day}_{shift_type}"


def sum_to_one(*args):
    return sum(args) == 1


def sum_to_n(n, *args):
    return sum(args) == n


def get_bqm(data, stitch_kwargs=None):

    csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.BINARY)

    start_date = datetime.strptime(str(data.find("StartDate").text), "%Y-%m-%d").date()
    end_date = datetime.strptime(str(data.find("EndDate").text), "%Y-%m-%d").date()
    num_of_days = (end_date - start_date).days + 1

    # one shift for same person per day
    for employee in data.find("Employees"):
        for day in range(num_of_days):
            labels = {
                get_label(employee.attrib["ID"], day, st.attrib["ID"])
                for st in data.find("ShiftTypes")
            }
            csp.add_constraint(sum_to_one, labels)

    # somebody every day
    for day in range(num_of_days):
        labels = {
            get_label(emp.attrib["ID"], day, st.attrib["ID"])
            for emp, st in product(data.find("Employees"), data.find("ShiftTypes"))
        }
        csp.add_constraint(sum_to_one, labels)

    # MaxSeq
    for employee in data.find("Employees"):
        for contract in employee:
            if data.find(f'.//Contract[@ID="{contract.text}"]/MaxSeq') is None:
                continue
            max_seq = int(
                data.find(f'.//Contract[@ID="{contract.text}"]/MaxSeq').attrib["value"]
            )
            for day in range(num_of_days - (max_seq - 1)):
                days = list(range(max_seq + 1))
                shifts = [st.attrib["ID"] for st in data.find("ShiftTypes")]
                labels = {
                    get_label(employee.attrib["ID"], day + i, st)
                    for i, st in product(days, shifts)
                }
                csp.add_constraint(lambda *args: sum(args) <= max_seq, labels)

    # FixedAssignments
    # for emp in data.find("FixedAssignments"):
    #     csp.fix_variable(
    #         get_label(
    #             emp.find("EmployeeID").text,
    #             int(emp.find(".//Assign/Day").text),
    #             emp.find(".//Assign/Shift").text,
    #         ),
    #         1,
    #     )

    # TODO
    # mark '-' as day off
    # use '$' as any shift

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

    # ShiftOffRequests
    for sf in data.find("ShiftOffRequests"):
        bqm.add_variable(
            get_label(
                sf.find("EmployeeID").text, sf.find("Day").text, sf.find("Shift").text
            ),
            int(sf.attrib["weight"]),
        )

    # ShiftOnRequests
    for sf in data.find("ShiftOnRequests"):
        bqm.add_variable(
            get_label(
                sf.find("EmployeeID").text, sf.find("Day").text, sf.find("Shift").text
            ),
            -int(sf.attrib["weight"]),
        )

    pruned_variables = list(bqm.variables)
    for employee in data.find("Employees"):
        for day in range(num_of_days):
            for st in data.find("ShiftTypes"):
                label = get_label(employee.attrib["ID"], day, st.attrib["ID"])
                bias = 1
                if label in pruned_variables:
                    bqm.add_variable(label, bias)

    return bqm


if __name__ == "__main__":
    file_name = "Instance_my.ros"
    full_file = os.path.abspath(os.path.join("instances1_24", file_name))
    data = ET.parse(full_file)

    bqm = get_bqm(data)
    print(bqm.to_qubo())
    # qpu
    # sampler = EmbeddingComposite(DWaveSampler(solver={"qpu": True}))
    # sampleset = sampler.sample(bqm, chain_strength=2.0, num_reads=1000)

    # cpu
    sampler = neal.SimulatedAnnealingSampler()
    sampleset = sampler.sample(bqm, num_reads=1000)

    solution1 = sampleset.first.sample

    selected_nodes = [
        k for k, v in solution1.items() if v == 1 and not k.startswith("aux")
    ]

    print("-" * 40)
    # print(bqm)
    print("-" * 40)

    pprint(sorted(selected_nodes))
