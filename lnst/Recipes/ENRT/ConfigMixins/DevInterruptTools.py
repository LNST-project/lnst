import re
from lnst.Controller.Recipe import RecipeError
from lnst.Controller.RecipeResults import ResultLevel


def pin_dev_interrupts(dev, cpus, policy=None):
    netns = dev.netns
    check_cpu_validity(netns, cpus)

    intrs = get_dev_interrupts(dev)

    for i, intr in enumerate(intrs):
        try:
            if policy in [ "round-robin", None ]:
                cpu = cpus[i % len(cpus)]
            elif policy == "all":
                cpu = ",".join([str(cpu) for cpu in cpus])

            netns.run(
                "echo -n {} > /proc/irq/{}/smp_affinity_list".format(cpu, intr)
            )
        except ValueError:
            pass

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
