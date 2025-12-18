#!/bin/bash

while getopts u:p:t: flag
do
    case "${flag}" in
        t) TOWER_IP=${OPTARG};;
        u) USERNAME=${OPTARG};;
        p) PASSWORD=${OPTARG};;
    esac
done

if [ -z "$USERNAME" ]; then
    echo "-u username is required"
    exit 1
fi
if [ -z "$PASSWORD" ]; then
    echo "-p password is required"
    exit 1
fi
if [ -z "$TOWER_IP" ]; then
    echo "-t tower's ip is required"
    exit 1
fi

TOKEN=$(curl -s -X POST \
    $TOWER_IP/v2/api/login \
    -H "Content-Type: application/json" \
    -d '{"username":"'$USERNAME'","password":"'$PASSWORD'","source":"LOCAL"}' | \
    jq -r ".data.token")
    
echo TOWER IP is $TOWER_IP
echo TOKEN is $TOKEN

CLUSTERS_RESPONSE=$(curl -s -X POST \
    ${TOWER_IP}/v2/api/get-clusters \
    -H "Authorization: ${TOKEN}" \
    -H "Content-Language: en-US" \
    -H "Content-Type: application/json")

readarray -t CLUSTERS < <(echo "${CLUSTERS_RESPONSE}" | jq -r '.[] | [.name, .hypervisor] | @tsv')

printf "%-4s %-20s %-20s\n" "[No.]" "[Cluster Name]" "[Hypervisor Type]"

for i in "${!CLUSTERS[@]}"; do
    NAME=$(echo "${CLUSTERS[$i]}" | awk -F $'\t' '{print $1}')
    HYPERVISOR=$(echo "${CLUSTERS[$i]}" | awk -F $'\t' '{print $2}')
    printf "%-4d %-20s %-20s\n" $((i+1)) "${NAME}" "${HYPERVISOR}"
done

while true; do
    read -p "Please enter the number [1-${#CLUSTERS[@]}]:" CHOICE

    if ! [[ $CHOICE =~ ^[0-9]+$ ]]; then
        echo "Invalid input. "
        continue
    fi

    if (( CHOICE >= 1 && CHOICE <= ${#CLUSTERS[@]} )); then
        CLUSTER_ID=$(echo "${CLUSTERS_RESPONSE}" | jq -r --argjson idx $((CHOICE-1)) '.[$idx].id')
        echo "CLUSTER ID is: ${CLUSTER_ID}"
        break
    else
        echo "Invalid input. "
    fi
done

function check_view_name() {
    curl -s -X POST \
        $TOWER_IP/v2/api/get-views \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
        -d '{"where":{"cluster":{"id":"'$CLUSTER_ID'"},"name":"'$1'"}}' | \
        grep $1
}

function get_view_id() {
    curl -s -X POST \
        $TOWER_IP/v2/api/get-views \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
        -d '{"where":{"cluster":{"id":"'$CLUSTER_ID'"},"name":"'$1'"}}' | \
        jq -r ".[].id"
}

function get_nodes() {
    local NODE_INFO=$(
        curl -s -X POST \
            $TOWER_IP/v2/api/get-hosts \
            -H "Authorization: $TOKEN" \
            -H "Content-Language: en-US" \
            -H "Content-Type: application/json" \
            -d '{"where":{"cluster":{"id":"'$CLUSTER_ID'"}}}'
    )
    NODE_COUNT=$(
        curl -s -X POST \
            $TOWER_IP/v2/api/get-hosts-connection \
            -H "Authorization: $TOKEN" \
            -H "Content-Language: en-US" \
            -H "Content-Type: application/json" \
            -d '{"where":{"cluster":{"id":"'$CLUSTER_ID'"}}}' | \
            jq -r ".aggregate.count"
    )

    for ((node=0; node<$NODE_COUNT; node++)); do
        NODE_ID[$node]=$(echo $NODE_INFO |jq -r ".["$node"].id")
    done
    NODE_ID=$(printf '%s\n' "${NODE_ID[@]}" | jq -R . | jq -s .)
    echo $NODE_ID
}

function create_view_dashboard() {
    CHECK_VIEW=$(check_view_name $1)
    if [ -z "$CHECK_VIEW" ]; then
        curl -X POST \
            $TOWER_IP/v2/api/create-view \
            -H "Authorization: $TOKEN" \
            -H "Content-Language: en-US" \
            -H "Content-Type: application/json" \
            -d '[{"time_unit":"HOUR","time_span":2,"cluster_id":"'$CLUSTER_ID'","name":"'$1'"}]'
        echo
        echo finish create view dashboard $1
    else
        echo "view dashboar named $1 is exist"
        exit 1
    fi
}

function create_graph_cluster() {
    local VIEW_ID=$(get_view_id Cluster)
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"cluster","view_id":"'$VIEW_ID'","title":"集群 CPU 使用率 %","cluster_id":"'$CLUSTER_ID'","connect_id":["'$CLUSTER_ID'"],"metric_name":"cluster_cpu_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"cluster","view_id":"'$VIEW_ID'","title":"集群 内存 使用率 %","cluster_id":"'$CLUSTER_ID'","connect_id":["'$CLUSTER_ID'"],"metric_name":"cluster_memory_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"cluster","view_id":"'$VIEW_ID'","title":"集群 已使用数据空间","cluster_id":"'$CLUSTER_ID'","connect_id":["'$CLUSTER_ID'"],"metric_name":"zbs_cluster_provisioned_data_space_bytes"}]'
    echo VIEW_ID $VIEW_ID
}

function create_graph_host() {
    local VIEW_ID=$(get_view_id Host)
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"主机 CPU 使用率 %","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"host_cpu_overall_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"分配给运行（含暂停）虚拟机逻辑核数量","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"elf_host_vcpus_provisioned_running"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"主机 CPU 温度","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"host_cpu_temperature_celsius"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"主机 内存 使用率 %","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"host_memory_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"缓存命中率 - 读","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"zbs_chunk_read_cache_hit_ratio"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"缓存命中率 - 写","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"zbs_chunk_write_cache_hit_ratio"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"已使用数据空间（物理）","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"zbs_chunk_used_data_space_bytes"}]'
    #curl -w "\n" -X POST \
	#    $TOWER_IP/v2/api/create-graph \
    #    -H "Authorization: $TOKEN" \
    #    -H "Content-Language: en-US" \
    #    -H "Content-Type: application/json" \
	#    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"管理网络网口之间丢包率 %","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"host_network_ping_packet_loss_percent_management"}]'
    #curl -w "\n" -X POST \
	#    $TOWER_IP/v2/api/create-graph \
    #    -H "Authorization: $TOKEN" \
    #    -H "Content-Language: en-US" \
    #    -H "Content-Type: application/json" \
	#    -d '[{"type":"AREA","resource_type":"host","view_id":"'$VIEW_ID'","title":"存储网络网口之间丢包率 &","cluster_id":"'$CLUSTER_ID'","connect_id":'"$NODE_ID"',"metric_name":"host_network_ping_packet_loss_percent_storage"}]'
    #    echo VIEW_ID $VIEW_ID
}

function create_graph_vm() {
    local VIEW_ID=$(get_view_id VM)
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"vm","metric_type":"TOPK","metric_count":"5","view_id":"'$VIEW_ID'","title":"虚拟机 CPU 使用率 Top N","cluster_id":"'$CLUSTER_ID'","connect_id":[],"metric_name":"elf_vm_cpu_overall_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"vm","metric_type":"TOPK","metric_count":"5","view_id":"'$VIEW_ID'","title":"虚拟机 CPU 就绪等待时间占比 Top N","cluster_id":"'$CLUSTER_ID'","connect_id":[],"metric_name":"elf_vm_cpu_overall_steal_time_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"vm","metric_type":"TOPK","metric_count":"5","view_id":"'$VIEW_ID'","title":"虚拟机 内存 使用率 Top N","cluster_id":"'$CLUSTER_ID'","connect_id":[],"metric_name":"elf_vm_memory_usage_percent"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"vm","metric_type":"TOPK","metric_count":"5","view_id":"'$VIEW_ID'","title":"虚拟机写带宽 Top N","cluster_id":"'$CLUSTER_ID'","connect_id":[],"metric_name":"elf_vm_disk_overall_write_speed_bps"}]'
    curl -w "\n" -X POST \
	    $TOWER_IP/v2/api/create-graph \
        -H "Authorization: $TOKEN" \
        -H "Content-Language: en-US" \
        -H "Content-Type: application/json" \
	    -d '[{"type":"AREA","resource_type":"vm","metric_type":"TOPK","metric_count":"5","view_id":"'$VIEW_ID'","title":"虚拟机 读写延迟 Top N","cluster_id":"'$CLUSTER_ID'","connect_id":[],"metric_name":"elf_vm_disk_overall_avg_read_write_latency_ns"}]'
    echo VIEW_ID $VIEW_ID
}


create_view_dashboard Cluster
create_view_dashboard Host
create_view_dashboard VM
create_graph_cluster
get_nodes
create_graph_host
create_graph_vm