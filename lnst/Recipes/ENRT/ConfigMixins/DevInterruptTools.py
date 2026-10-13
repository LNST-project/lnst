import re
import logging
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel


def pin_dev_interrupts(dev, cpus, policy=None):
    netns = dev.netns
    check_cpu_validity(netns, cpus)

    intrs = get_dev_interrupts(dev)

    for i, intr in enumerate(intrs):
        try:
            if policy in [ "round-robin", None ]:
                requested_cpus = [cpus[i % len(cpus)]]
            elif policy == "all":
                requested_cpus = cpus

            netns.run(
                "echo -n {} > /proc/irq/{}/smp_affinity_list".format(
                    ",".join(str(cpu) for cpu in requested_cpus), intr
                )
            )

            check_effective_affinity(netns, intr, requested_cpus)
        except ValueError:
            pass


def check_effective_affinity(netns, intr, requested_cpus):
    res = netns.run(
        "cat /proc/irq/{}/effective_affinity_list".format(intr),
        job_level=ResultLevel.DEBUG,
    )

    effective_cpus = parse_cpu_list(res.stdout)

    if not effective_cpus.issubset(set(requested_cpus)):
        logging.warning(
            "IRQ {} effective affinity {} does not match requested affinity "
            "{}; the kernel reassigned it to a different CPU within the "
            "applicable cpumask.".format(
                intr, sorted(effective_cpus), sorted(requested_cpus)
            )
        )

def parse_cpu_list(cpu_list):
    cpus = set()
    for part in cpu_list.strip().split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-")
            cpus.update(range(int(start), int(end) + 1))
        else:
            cpus.add(int(part))
    return cpus


def check_cpu_validity(host, cpus):
    cpu_info = host.run("lscpu", job_level=ResultLevel.DEBUG).stdout
    regex = r"CPU\(s\): *([0-9]*)"
    num_cpus = int(re.search(regex, cpu_info).groups()[0])
    for cpu in cpus:
        if cpu < 0 or cpu > num_cpus - 1:
            raise RecipeError(
                "Invalid CPU value given: %d. Accepted value %s."
                % (
                    cpu,
                    "is: 0" if num_cpus == 1 else "are: 0..%d" % (num_cpus - 1),
                )
            )

def get_dev_interrupts(dev):
    if "up" not in dev.state:
        # device needs to be UP when grepping /proc/interrupts
        dev.up()
        set_down = True
    else:
        set_down = False

    if dev.bus_info:
        dev_id_regex = r"({})|({})".format(dev.name, dev.bus_info)
    else:
        dev_id_regex = r"{}".format(dev.name)

    res = dev.netns.run(
        "grep -P \"{}\" /proc/interrupts | cut -f1 -d: | sed 's/ //'".format(
            dev_id_regex
        ),
        job_level=ResultLevel.DEBUG,
    )

    if set_down:
        # set device back down if we set it up
        dev.down()

    return [
        int(intr.strip())
        for intr in res.stdout.strip().split("\n")
        if intr != ""
    ]
