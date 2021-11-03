# FaaSim Cloud/Edge Severless Platform Simulator V1.0


import random
import time

class Event:
    origin_zone = -1  # ID of the zone or region where the event is originated (Values 1, 2, ...)
    assigned_zone = -1 # ID of the zone or region assigned to execute the event (zone 0 is the cloud; zones 1, 2, 3 are edge zones)
    init_time = 0 # Time when the request arrives to the serverless platform (init_time + RTT/2)
    end_time = 0 # Time when the execution of the request ends in the serverless platform
    total_time = 0 # Total response time for the serverless platform point of view: total_time = end_time - init_time
    rtt = 0 # RTT observed for this request
    total_time_with_rtt = 0 # total_time + rtt --> response time for the client point of view
    resource_usage = []


class Resource:
    busy_init_time = 0 # Time when the resource starts to be busy
    busy_end_time = 0 # Time when the resource ends to be busy
    warm_init_time = 0 # time when the resource start to be warm after booting or after being busy
    warmingup_ready = 0 # Time when a warming-up resource is ready to be used
    keep_warm = 0 # If keep_warm==1 it is a pre-warmed resource (should never be cold-down)

def create_event_list():
# This function can create an synthetic event_list.txt file
# with events_per_second events uniformly distributed
# each event assigned to a zone

    file = open('event_list.txt', 'w')
    interval = 1.0 / float(events_per_second)
    zone = 0
    for t in range(sim_time):
        for e in range(events_per_second):
            time = float(t) + float(e) * interval
            # print(time, zone)
            file.write("%.15f %i\n" % (time, zone))
            zone += 1
            if zone >= num_zones:
                zone = 0
    file.close()


def read_event_list():
# This functions reads the file event_list.txt
# This file contains a time-ordered list of events, one per line.
# Each line includes two data:
#   - The init time of the event
#   - The zone where the event was generated

# Per every second, s, the function creates a ordered list of events, called event_list[s],
# with all the events that start in the time t, with s <= t < s+1

# This function returns the simulation time (sim_time)

    end_time=0
    # First we create an empty event list
    for i in range(max_sim_time):
        event_list.append([])

    file = open('event_list.txt', 'r')
    for line in file:
        data = []
        # We introduce in "data" the values of every line of the file
        # data[0] contains the time and data[1] contains the zone
        data = list(line.split(" "))
        # Create a new event
        event = Event()
        event.init_time = float(data[0])
        second = int(event.init_time)
        if event.init_time > float(max_sim_time):
            print("ERROR!! Max. Simulation time exceeded")
            exit(-1)
            break
        if event.init_time > end_time:
            end_time = event.init_time+1
        event.origin_zone = int(data[1])
        second = int(event.init_time)
        event_list[second].append(event)
    file.close()
    return(end_time)


def initalize_resource_list():
# We create three lists of resources for every zone:
# warm_resources; busy_resources; warming_up resources
# Ej. warm_resources[z][r] --> resource r (warm) from zone z
# warm_resources = [] # List of warm resources. One list per zone z. E.g.: warm_resources[z][r]
# busy_resources = [] # List of busy resources. One list per zone z. E.g.: busy_resources[z][r]
# warmingup_resources = [] # List of warming up resources. One list per zone z. E.g.: warmingup_resources[z][r]
# total_used_resources = [] # Total used resources per zone (warm + busy + warmingup)
    resource_id = 0
    for z in range(num_zones+1):
        warm_resources.append([])
        busy_resources.append([])
        warmingup_resources.append([])
        resource_usage_time.append(0)
        resource_busy_time.append(0)
        resource_exec_time.append(0)
        resource_idle_time.append(0)
        number_of_cold_starts.append(0)
        if z < num_zones: # warm resources in edge zones
            prewarming = min(edge_prewarming, max_edge_resources)
        else:
            prewarming = cloud_prewarming
        for r in range(prewarming):
            resource = Resource()
            resource.boot_time = 0
            resource.warm_init_time = 0
            resource.keep_warm = 1
            warm_resources[z].append(resource)
        resource_usage_num_avg.append([])
        resource_usage_num_max.append([])
        for t in range(sim_time):
            resource_usage_num_avg[z].append(0)
            resource_usage_num_max[z].append(0)


def sched_policy_0(event):
# Policy 0 --> schedule first in the local edge zone
# If there are no resources available in the local zone, the schedule in the cloud
# If there are warm resources, we move the resource from "warm" to "busy" list
# Else a new resource is booted
# It returns the assigned zone, and the end_time of the execution of the task in the assigned zone

    zone = event.origin_zone

    # First, we check if there are enough free resources in the local zone
    if len(busy_resources[zone]) < max_edge_resources: # Schedule in the local edge zone
        assigned_zone = zone
    else: # Schedule in the cloud zone
        assigned_zone = cloud_zone

    return assigned_zone


def sched_policy_1(event):
# Policy 1 --> schedule first where there are warm resources (cloud or edge), then in the local zone
# If there are no resources available in the local zone, the schedule in the cloud
# If there are warm resources, we move the resource from "warm" to "busy" list
# Else a new resource is booted
# It returns the assigned zone, and the end_time of the execution of the task in the assigned zone

    zone = event.origin_zone

# First, we check if there are enough free resources in the local zone
    assigned = 0
    if len(busy_resources[zone]) < max_edge_resources: # There are free resources in the local zone
        if len(warm_resources[zone]) > 1: # There are warm resources in the local edge zone
            assigned_zone = zone
        elif len(warm_resources[num_zones]) > 1: # There are warm resources in the cloud zone
            assigned_zone = cloud_zone
        else: # No warm resources available ==> then boot a cold resource from local zone
            assigned_zone = zone
    else:  # No free resources in local zone ==> Schedule in the cloud zone
        assigned_zone = cloud_zone

    return assigned_zone

def allocate_resource(event):
    global sim_end_time
# This function allocate a resource from the assigned zone for executing the event
# If there is some warm resource available, it is selected
# Otherwise, if there is some warming-up resource, it is selected
# Otherwise, a new (cold) resource is booted

    origin_zone = event.origin_zone
    assigned_zone = event.assigned_zone
    init_time = event.init_time

    cold_start = cold_start_time * (1 + random.uniform(-1, 1) * cold_start_variance / 100)
    warm_start = warm_start_time * (1 + random.uniform(-1, 1) * warm_start_variance / 100)
    exec = exec_time * (1 + random.uniform(-1, 1) * exec_time_variance / 100)

    if origin_zone == assigned_zone:
        rtt_latency = (edge_rtt_latency * (1 + random.uniform(-1, 1) * edge_rtt_variance / 100))/1000
    else: # Schedule in the cloud zone
        rtt_latency = (cloud_rtt_latency * (1 + random.uniform(-1, 1) * cloud_rtt_variance / 100))/1000

    # Look for a warm resource in the assigned zone.
    if len(warm_resources[assigned_zone]) > 0:
        resource = warm_resources[assigned_zone].pop(0)
        end_time = init_time + float(exec + warm_start) / 1000.0
    #  If no warm resource found, we first look for any warming-up resource in the assigned zone.
    elif len(warmingup_resources[assigned_zone]) > 0:
        resource = warmingup_resources[assigned_zone].pop(0)
        end_time = max(resource.warmingup_ready, init_time) + float(exec + warm_start) / 1000.0
    #  If no warm nor warming-up resource found, the we start a new (cold) resource in the assigned zone.
    else:
        resource = Resource()
        end_time = init_time + float(exec + cold_start) / 1000.0
        resource.boot_time = init_time
        resource.keep_warm = 0 # It is not a pre-warmed resource
        number_of_cold_starts[assigned_zone] = number_of_cold_starts[assigned_zone] + 1

    resource.busy_init_time = init_time
    resource.busy_end_time = end_time
    busy_resources[assigned_zone].append(resource)
    resource_busy_time[assigned_zone] = resource_busy_time[assigned_zone] + end_time - init_time
    resource_exec_time[assigned_zone] = resource_exec_time[assigned_zone] + float(exec)/1000.0

    event.end_time = end_time
    event.total_time = end_time - init_time
    event.rtt = rtt_latency
    event.total_time_with_rtt = event.total_time + event.rtt

    if sim_end_time < end_time:
        sim_end_time = end_time

    return event

def update_resource_list(time):
# This function checks:
#  - if some busy resource should pass to warm
#  - if any  booting (warming up) resources should pass to warm
#  - if any warm resources should be shut-down


    for z in range(num_zones+1):
        # Check if any busy resources should pass to warm
        i = 0
        while i < len(busy_resources[z]):
            if time > (busy_resources[z][i].busy_end_time + reuse_interval/1000):
                resource = busy_resources[z].pop(i) # the resource pass to warm list
                resource.warm_init_time = resource.busy_end_time + reuse_interval/1000
                warm_resources[z].append(resource)
            else:
                i = i + 1
        # Check if any  booting (warming up) resources should pass to warm
        i = 0
        while i < len(warmingup_resources[z]):
            if time > warmingup_resources[z][i].warmingup_ready:
                resource = warmingup_resources[z].pop(i)  # the resource pass to warm list
                resource.warm_init_time = resource.warmingup_ready
                warm_resources[z].append(resource)
            else:
                i = i + 1

        # Check if any warm resources should be cold-down according to pre-warming policies
        # Pre-warming policy 0 --> Fixed pre-warming ==> Pre-warmed resources (with keep_warm==1) are never cold-down
        if prewarming_policy == 0:
            i = 0
            while i < len(warm_resources[z]):
                cold_down_time = warm_resources[z][i].warm_init_time + float(keep_alive_interval) / 1000.0
                if (warm_resources[z][i].keep_warm == 0) and (time > cold_down_time):
                    resource = warm_resources[z].pop(i)  # the resource pass to cold state and it is removed from any list
                    resource_usage_time[z] = resource_usage_time[z] + (cold_down_time - resource.boot_time)
                else:
                    i = i + 1

        # Pre-warming policy 1 --> Adaptive pre-warming ==> pre-warm resources on every zone to reach prewarming value
        if prewarming_policy == 1:
            if z < num_zones:
                prewarming = min(edge_prewarming, max_edge_resources)
            else:
                prewarming = cloud_prewarming
            diff = prewarming - (len(warm_resources[z]) + len(warmingup_resources[z]))
            if diff < 0:  # Check if some warm resource can be cold down
                max_cold_down = - diff  # no more than max_cold_down resources should be cold down to guarantee prewarming
                cold_down = 0
                i = 0
                while i < len(warm_resources[z]):
                    cold_down_time = warm_resources[z][i].warm_init_time + float(keep_alive_interval) / 1000.0
                    if (warm_resources[z][i].keep_warm == 0) and (time > cold_down_time):
                        resource = warm_resources[z].pop(i)  # the resource pass to cold state and it is remove from any list
                        resource_usage_time[z] = resource_usage_time[z] + (cold_down_time - resource.boot_time)
                        #   resource_idle_time[z] = resource_idle_time[z] + (time - resource.warm_init_time)
                        cold_down = cold_down + 1
                    else:
                        i = i + 1
                    if cold_down >= max_cold_down:
                        break
            if diff > 0:  # if diff > 0 ==> No enough warm resources, then warm up "diff" new resources
                for i in range(diff):
                    resource = Resource()
                    resource.boot_time = time
                    resource.keep_warm = 0
                    resource.warmingup_ready = time + prewarming_time * (1 + random.uniform(-1, 1) * cold_start_variance / 100) / 1000.0
                    warmingup_resources[z].append(resource)


def process_event(time, event_num):
# This function is responsible for processing each event
# It first determines wich is the assigned zone, according to the scheduling policy selected
# Then, it allocates a resource from the assigned zone

    event=event_list[time][event_num]

    if sched_policy == 1:
        # Policy 1 --> schedule first where there are warm resources (cloud or edge), if not, in the local zone
        #assigned_zone, end_time = sched_policy_1(origin_zone, init_time)
        event.assigned_zone = sched_policy_1(event)
    else:
        # Policy 0 --> schedule first in the local zone
        #assigned_zone, end_time = sched_policy_0(origin_zone, init_time)
        event.assigned_zone = sched_policy_0(event)

    update_resource_list(event.init_time)
    event = allocate_resource(event)
    event_list[time][event_num] = event

    # Compute how many resources are being used when this event is processed
    # then add this number to the total number of resources used in this zone, to compute, later, the average
    for z in range(num_zones+1):
        num_used_resources = len(warmingup_resources[z]) + len(warm_resources[z]) + len(busy_resources[z])
        resource_usage_num_avg[z][time] = resource_usage_num_avg[z][time] + num_used_resources
        resource_usage_num_max[z][time] = num_used_resources


def compute_resource_usage():
# This function is responsible for computing and print the resource usage time

    # Compute first resource usage time per zone
    total_usage_time = 0
    total_busy_time = 0
    total_idle_time = 0
    total_exec_time = 0
    total_number_of_cold_starts = 0
    # Update the resource usage with the resources that remain warm or warming-up at the end of the simulation
    for z in range(num_zones+1):
        for i in range(len(warm_resources[z])):
            resource_usage_time[z] = resource_usage_time[z] + (sim_end_time - warm_resources[z][i].boot_time)
         #   resource_idle_time[z] = resource_idle_time[z] + (sim_end_time - warm_resources[z][i].warm_init_time)
        for i in range(len(warmingup_resources[z])):
            resource_usage_time[z] = resource_usage_time[z] + (sim_end_time - warmingup_resources[z][i].boot_time)
        # print("Resource usage time for zone", z, "-->", resource_usage_time[z], "s")
        resource_usage_time[z] =  float(resource_usage_time[z])/3600.0 # Pass seconds to hours
        resource_busy_time[z] =  float(resource_busy_time[z])/3600.0 # Pass seconds to hours
        resource_exec_time[z] =  float(resource_exec_time[z])/3600.0 # Pass seconds to hours
        resource_idle_time[z] = resource_usage_time[z] - resource_busy_time[z]

        total_usage_time = total_usage_time + resource_usage_time[z] # in hours
        total_busy_time = total_busy_time + resource_busy_time[z] # in hours
        total_idle_time = total_idle_time + resource_idle_time[z]  # in hours
        total_exec_time = total_exec_time + resource_exec_time[z]  # in hours
        total_startup_time = total_busy_time - total_exec_time  # in hours
        total_number_of_cold_starts = total_number_of_cold_starts + number_of_cold_starts[z]

    for z in range(num_zones + 1):
        resource_usage_time[z] = round(resource_usage_time[z], 2)
        resource_busy_time[z] = round(resource_busy_time[z], 2)
        resource_idle_time[z] = round(resource_idle_time[z], 2)
    print("\n")
    print("Total Resource usage time per zone:")
    print(resource_usage_time, "hours") # in hours
    print("Total resource busy time per zone (includes execution + start-up time):")
    print(resource_busy_time, "hours") # in hours
    print("Total resource idle time per zone:")
    print(resource_idle_time, "hours")  # in hours
    print("\n")

    print("Total resource usage time -->", "{:.2f}".format(total_usage_time), "hours")
    print("Total resource startup time -->", "{:.2f}".format(total_startup_time), "hours")
    print("Total resource exec time -->", "{:.2f}".format(total_exec_time), "hours")
    print("Total resource idle time -->", "{:.2f}".format(total_idle_time), "hours")
    print("\nTotal number of cold starts -->", total_number_of_cold_starts)

    # Compute then number of resources used, in average, every second, per zone
    average_per_zone = []
    total = 0
    max = 0
    for z in range(num_zones+1):
        average_per_zone.append(0)
        for t in range(sim_time):
            if len(event_list[t]) > 0:
                resource_usage_num_avg[z][t] = resource_usage_num_avg[z][t] / len(event_list[t])
            else:
                resource_usage_num_avg[z][t] = 0
            average_per_zone[z] = average_per_zone[z] + resource_usage_num_avg[z][t]
            if resource_usage_num_max[z][t] > max:
                max = resource_usage_num_max[z][t]
        average_per_zone[z] = average_per_zone[z] / sim_time
        total = total + average_per_zone[z]
    print("Average number of resources used per second -->", "{:.2f}".format(total))
    print("Max number of simultaneous resources used -->", max)

def simulation():
# This funcions process one-by-one all the events in the event list

    total_time = 0.0 # Sum of response times for all tasks from the serverless platformm point of view
    client_total_time = 0.0  # Sum of response times for all tasks from the client point of view
    min_time = 99999.0 # Task with minimum response time
    max_time = 0.0 # Task with maximum response time
    min_client_time = 99999.0  # Task with minimum response time
    max_client_time = 0.0  # Task with maximum response time
    total_tasks = 0
    for t in range(sim_time):
        for event_num in range(len(event_list[t])):
            process_event(t, event_num)
            total_tasks = total_tasks + 1
            task_time = event_list[t][event_num].total_time
            client_task_time = event_list[t][event_num].total_time_with_rtt
            total_time = total_time + task_time
            client_total_time = client_total_time + client_task_time
            if task_time < min_time:
                min_time = task_time
            if task_time > max_time:
                max_time = task_time
            if client_task_time < min_client_time:
                min_client_time = client_task_time
            if client_task_time > max_client_time:
                max_client_time = client_task_time
        minutes = int(t / 60)
        seconds = t - (minutes * 60)
        if seconds == 59:
            print(" -- simulated", minutes + 1, "min.")
    average_time = 1000.0 * total_time / float(total_tasks)
    min_time = 1000.0 * min_time
    max_time = 1000.0 * max_time

    average_client_time = 1000.0 * client_total_time / float(total_tasks)
    min_client_time = 1000.0 * min_client_time
    max_client_time = 1000.0 * max_client_time

    update_resource_list(sim_end_time)
    compute_resource_usage()

    print("\nSimulation end time:", sim_end_time)

    print("\nServerless platform response time:")
    print("  - Average task response time --> ", "{:.2f}".format(average_time), "ms")
    print("  - Min. task response time --> ", "{:.2f}".format(min_time), "ms")
    print("  - Max. task response time --> ", "{:.2f}".format(max_time), "ms")

    print("\nClient-side  response time:")
    print("  - Average task response time --> ", "{:.2f}".format(average_client_time), "ms")
    print("  - Min. task response time --> ", "{:.2f}".format(min_client_time), "ms")
    print("  - Max. task response time --> ", "{:.2f}".format(max_client_time), "ms")


def store_event():
# This function stores each processed event into a output file
# The output file contains, for each event, the response time for the platform and for the client
    file = open('event_output.txt', 'w')
    file2 = open('response_time.txt', 'w')

    n = 0
    for t in range(sim_time):
        for event in event_list[t]:
            file.write("Event %i --> Init: %.2f s. - End: %.2f - Total %.1f ms (For client --> Total %.1f ms )\n" % (n, event.init_time, event.end_time, 1000*event.total_time, 1000*event.total_time_with_rtt))
            file2.write("%.2f\n" % (1000*event.total_time))
            n += 1
    file.close()
    file2.close()


# INPUT PARAMETERS FOR THE MODEL
# Note that, in this version of FaaSim, all the inputs parameters are hard-coded

# SIMULATION TIME
max_sim_time = 24 * 60 * 60 # Max sim time = 1 day
sim_end_time = 0 # Time when the last event finish its execution

#INPUT DATA
create_input_data = 0   # If 0 --> read default input data file (event_list.txt)
                        # If 1 --> create a new input data file according to the next parameters: sim_time and events_per_second
sim_time = 10           # If create_input_data==1, use this sim_time
events_per_second = 100   # Create an input event_list.txt file with this number of events_per_second (uniformly distributed) and sim_time duration

num_zones = 5
cloud_zone = num_zones

# POLICIES
# Scheduling policies (sched_policy)
# 0 --> edge-firt policy (schedule first in the edge zone, if not resources are avaiable in the edge, then schedule in the cloud)
# 1 --> warm-first policy (schedule first where there are warm resources, then in the edge zone)
sched_policy = 1

# Pre-warming policies
# If prewarming_policy == 0 ==> Fixed pre-warming: we prewarm N resources, and if more resources are needed, they are booted on-demand
# If prewarming_policy == 1 ==> Adaptive pre-warming: we prewarm N resources. When the number available prewarmed resources is lower that N, we prewarm more resources
prewarming_policy = 0

# Num. of resources prewarmed:
edge_prewarming = 0 # resources prewarmed per edge zone
cloud_prewarming = 160 # resources prewarmed in the central cloud
# Keep_alive period (for instance reuse mechanism)
keep_alive_interval = 30000 # If a warm resource is unused for this period (in ms), the resource is cold down
reuse_interval = 0 # When a warm resource becomes idle, it can be reused after this interval

# Resource limit
max_edge_resources = 1000000 # Max. number of resources available at each edge zone

# DELAYS
exec_time = 2053 # Execution delay in ms (guessed value, it depends on the application)
cold_start_time = 6090 # Average cold start delay in ms
warm_start_time = 71 # Average warm start delay in ms
prewarming_time =  cold_start_time - warm_start_time # Time needed for booting pre-warmed instances (we assume that it is equal to cold_start - warm_start)
exec_time_variance = 1 # Variance (%) applied to cold start
cold_start_variance = 1 # Variance (%) applied to cold start
warm_start_variance = 4 # Variance (%) applied to warm start

edge_rtt_latency = 62 # RTT latencies (ms) between users and resources from local edge zone
edge_rtt_variance = 15 # Variance (%) applied to edge RTT latencies
cloud_rtt_latency = 851 # RTT latencies (ms) between users and resources from central cloud
cloud_rtt_variance = 5 # Variance (%) applied to cloud RTT latencies


# OTHER GLOBAL VARIABLES
#   Cloud is assumed to be the last zone
#   (e.g. for 4 zones: zones #0, #1, #2, #3 are the edge zones;  and zone #4 is the cloud)
event_list = []
resource_list = []
warm_resources = [] # List of warm resources. One list per zone z. E.g.: warm_resources[z][r]
busy_resources = [] # List of busy resources. One list per zone z. E.g.: busy_resources[z][r]
warmingup_resources = [] # List of warming up resources. One list per zone z. E.g.: warmingup_resources[z][r]
resource_usage_time = [] # Total resource usage time per zone (idle + exec + startup states)
resource_busy_time = [] # Total resource busy time per zone (includes exec+startup state)
resource_exec_time = [] # Total resource execution time per zone (include only execution time)
resource_idle_time = [] # Total idle resource time per zone (only idle state)
resource_usage_num_avg = [] # Average number of resources used every second per zone (warm + busy + warmingup)
resource_usage_num_max = [] # Max number of resources used every second per zone (warm + busy + warmingup)
number_of_cold_starts = [] # Number od cold starts per zone

# START THE MAIN CODE
print("Reading input files ......")

now = time.time()
sim_time = int(read_event_list())
initalize_resource_list()

execution_time = time.time() - now

print("Done (", "{:.2f}".format(execution_time), "s.)")
print("Starting Simulation ......")
now = time.time()

# Perform the simulation
simulation()

execution_time = time.time() - now
print("(Simulation time:", "{:.2f}".format(execution_time), "s.)")
store_event()
