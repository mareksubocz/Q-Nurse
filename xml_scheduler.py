import untangle
import os
from datetime import date, datetime
from itertools import product

import neal
import dwavebinarycsp
from dwave.system.composites import EmbeddingComposite
from dwave.system.samplers import DWaveSampler

from pprint import pprint
from collections import defaultdict

# TODO: wszyscy mają tylko dwa kontrakty - all i swój
# TODO: FixedAssignment jest zawsze na minus


def get_label(nurseID, day, shift_type):
    return f"{nurseID}_{day}_{shift_type}"


def sum_to_one(*args):
    return sum(args) == 1


def sum_to_n(n, *args):
    return sum(args) == n


def find_el_with_attrib(elements, attrib, value):
    return next(filter(lambda x: x[attrib] == value, elements), None)


def get_bqm(data, stitch_kwargs=None):
    """
    constraints are numbered according to constraint numbering in
    http://www.schedulingbenchmarks.org/papers/computational_results_on_new_staff_scheduling_benchmark_instances.pdf
    """
    csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.BINARY)

    start_date = datetime.strptime(data.StartDate.cdata, "%Y-%m-%d").date()
    end_date = datetime.strptime(data.EndDate.cdata, "%Y-%m-%d").date()
    num_of_days = (end_date - start_date).days + 1

    # TODO: 3, 4, 6, 7, 8, 9, 10

    # Setting up quick access to valid shifts
    validShifts = {}
    for employee in data.Employees.Employee:
        validShifts[employee['ID']] = set(find_el_with_attrib(
            data.Contracts.Contract,
            'ID',
            employee.ContractID[1].cdata
        ).ValidShifts['shift'].split(',')[:-1])

    # (1) one shift for same person per day
    for employee in data.Employees.Employee:
        for day in range(num_of_days):
            labels = {get_label(employee["ID"], day, st)
                      for st in validShifts[employee['ID']]}
            csp.add_constraint(sum_to_one, labels)

    # (2) no not_before violation
    not_before = defaultdict(set)
    for shift in data.ShiftTypes.Shift:
        hours, minutes = map(int, shift.StartTime.cdata.split(":"))
        for shift_next in data.ShiftTypes.Shift:
            if shift["ID"] == shift_next['ID']:
                continue
            hoursn, minutesn = map(int, shift_next.StartTime.cdata.split(":"))
            minutes += int(shift_next.Duration.cdata)
            minutes += int(data.Contracts.Contract[0].MinRestTime.cdata)
            hours += minutes // 60 - 24
            minutes = minutes % 60
            if (hours, minutes) > (hoursn, minutesn):
                not_before[shift['ID']].add(shift_next['ID'])

    allowed = {(0, 0), (1, 0), (0, 1)}
    for employee in data.Employees.Employee:
        for day in range(num_of_days - 1):
            for shift in validShifts[employee['ID']]:
                for fst in not_before[shift] & validShifts[employee['ID']]:
                    csp.add_constraint(
                        allowed,
                        {
                            get_label(employee, day, shift),
                            get_label(employee, day + 1, fst),
                        }
                    )

   # (3) maximum number of shifts that can be assigned by type
    # TODO: not found in instances yet

    # (4) Minimum and maximum work time

    # (5) Maximum Consecutive Shifts
    for employee in data.Employees.Employee:
        contract = find_el_with_attrib(
            data.Contracts.Contract, "ID", employee.ContractID[1].cdata
        )
        # if "MaxSeq" not in dir(contract):
            # continue
        max_seq = int(contract.MaxSeq['value'])
        for day in range(num_of_days - (max_seq - 1)):
            days = list(range(max_seq + 1))
            labels = {
                get_label(employee["ID"], day + i, st)
                for i, st in product(days, validShifts[employee['ID']])
            }
            csp.add_constraint(lambda *args: sum(args) <= max_seq, labels)

    # (6) Minimum Consecutive Shifts
    for employee in data.Employees.Employee:
        contract = find_el_with_attrib(
            data.Contracts.Contract, "ID", employee.ContractID[1].cdata
        )
        min_seq = int(find_el_with_attrib(contract.MinSeq, 'shift', '$')['value'])
        # TODO jak to sprawdzić

    # (7) Minimum Consecutive Days Off

    # (8) Maximum nubmer of weekends

    # (9) FixedAssignments, in paper descibed as days off
    for emp in data.FixedAssignments.Employee:
        for shift in validShifts[emp.EmployeeID.cdata]:
            csp.fix_variable(
                get_label(
                    emp.EmployeeID.cdata,
                    emp.Assign.Day.cdata,
                    shift,
                ),
                0,
            )

    # somebody every day
    for day in range(num_of_days):
        labels = {
            get_label(emp.attrib["ID"], day, st.attrib["ID"])
            for emp, st in product(data.find("Employees"), data.find("ShiftTypes"))
        }
        csp.add_constraint(sum_to_one, labels)

    # TODO
    # mark '-' as day off
    # use '$' as any shift
    # no more than maxShifts
    # for nurse_key, nurse_value in nurses.items():
    #     labels = set()
    #     for st in shift_types.keys():
    #         for day in range(horizon):
    #             labels.add(get_label(nurse_key, day, st))
    #     csp.add_constraint(
    #         lambda *args: le(nurse_value.maxShifts[st], sum(args)), labels)

    if stitch_kwargs is None:
        stitch_kwargs = {}
    bqm = dwavebinarycsp.stitch(csp, **stitch_kwargs)

    # ShiftOffRequests
    for sf in data.ShiftOffRequests.ShiftOff:
        bqm.add_variable(
            get_label(
                sf.EmployeeID.cdata,
                sf.Day.cdata,
                sf.Shift.cdata
            ),
            int(sf['weight'])
        )

    # ShiftOnRequests
    for sf in data.ShiftOnRequests.ShiftOn:
        bqm.add_variable(
            get_label(
                sf.EmployeeID.cdata,
                sf.Day.cdata,
                sf.Shift.cdata
            ),
            -int(sf['weight'])
        )

    pruned_variables = list(bqm.variables)
    for employee in data.Employees.Employee:
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
    # data = ET.parse(full_file)
    data = untangle.parse("it/Q-Nurse/instances1_24/Instance24.ros")
    data = data.SchedulingPeriod
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
