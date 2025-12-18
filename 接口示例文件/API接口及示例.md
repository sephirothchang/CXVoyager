> **许可证**：本文档依据 [GNU GPLv3](../LICENSE) 授权发布。

# 01-准备阶段，解析规划表，验证网络连通性，检查依赖环境
  ## 扫描主机信息，获取主机软件硬件等信息
  响应信息见扫描主机响应示例

  import requests
  import json

  host_ip = "10.0.20.204"

  url = f"http://{host_ip}/api/v2/deployment/host"

  payload = {}
  headers = {
    'host': host_ip,
    'content-type': 'application/json',
    'x-smartx-token': 'e79b85fc18b7402fbcc0391fe8d7d24c'
  }

  response = requests.request("GET", url, headers=headers, data=payload)

  print(response.text)


  ## 扫描集群信息，获取集群信息
  响应信息见扫描集群响应示例
  扫描集群接口通过某一主机存储网卡进行二层扫描，如果是LACP或者vlan子接口，是扫描不到其他主机的，会无返回值
  所以不推荐使用扫描集群接口，因为主机IP全部已知，可以通过逐台扫描主机接口从而获取所有主机的信息

  import requests
  import json

  host_ip = "10.0.20.204"

  url = f"http://{host_ip}/api/v2/deployment/cluster"

  payload = {}
  headers = {
    'host': host_ip,
    'content-type': 'application/json',
    'x-smartx-token': 'e79b85fc18b7402fbcc0391fe8d7d24c'
  }

  response = requests.request("GET", url, headers=headers, data=payload)

  print(response.text)



# 02-初始化集群
  ## 部署集群

  import requests
  import json

  host_ip = "10.0.20.204"

  url = f"http://{host_ip}/api/v2/deployment/cluster"

  payload = json.dumps({
    "platform": "kvm",
    "cluster_name": "HCI-01",
    "dns_server": [
      "127.0.0.1"
    ],
    "vdses": [
      {
        "name": "VDS-MGT",
        "bond_mode": "active-backup",
        "hosts_associated": [
          {
            "host_uuid": "1f967a52-9ac8-11f0-9b61-05cf1b7143e4",
            "nics_associated": [
              "ens224",
              "ens192"
            ]
          },
          {
            "host_uuid": "1ef75076-9ac8-11f0-838d-1320f7e67d81",
            "nics_associated": [
              "ens224",
              "ens192"
            ]
          },
          {
            "host_uuid": "1f97a2d8-9ac8-11f0-978c-3b1611b8ef4a",
            "nics_associated": [
              "ens224",
              "ens192"
            ]
          }
        ]
      },
      {
        "name": "VDS-SDS",
        "bond_mode": "active-backup",
        "hosts_associated": [
          {
            "host_uuid": "1f967a52-9ac8-11f0-9b61-05cf1b7143e4",
            "nics_associated": [
              "ens256",
              "ens161"
            ]
          },
          {
            "host_uuid": "1ef75076-9ac8-11f0-838d-1320f7e67d81",
            "nics_associated": [
              "ens256",
              "ens161"
            ]
          },
          {
            "host_uuid": "1f97a2d8-9ac8-11f0-978c-3b1611b8ef4a",
            "nics_associated": [
              "ens256",
              "ens161"
            ]
          }
        ]
      }
    ],
    "networks": [
      {
        "name": "mgt-network",
        "attached_vds": "VDS-MGT",
        "network_type": "mgt",
        "network_config": {
          "service": [
            {
              "host_uuid": "1f967a52-9ac8-11f0-9b61-05cf1b7143e4",
              "service_interface_name": "port-mgt",
              "service_interface_ip": "10.0.20.204",
              "netmask": "255.255.255.0"
            },
            {
              "host_uuid": "1ef75076-9ac8-11f0-838d-1320f7e67d81",
              "service_interface_name": "port-mgt",
              "service_interface_ip": "10.0.20.205",
              "netmask": "255.255.255.0"
            },
            {
              "host_uuid": "1f97a2d8-9ac8-11f0-978c-3b1611b8ef4a",
              "service_interface_name": "port-mgt",
              "service_interface_ip": "10.0.20.206",
              "netmask": "255.255.255.0"
            }
          ],
          "route": [
            {
              "gateway": "10.0.20.1"
            }
          ]
        },
        "mode": {
          "type": "vlan_access",
          "network_identities": [
            0
          ]
        }
      },
      {
        "name": "storage-network",
        "attached_vds": "VDS-SDS",
        "network_type": "storage",
        "network_config": {
          "service": [
            {
              "host_uuid": "1f967a52-9ac8-11f0-9b61-05cf1b7143e4",
              "service_interface_name": "port-storage",
              "service_interface_ip": "10.0.21.204",
              "netmask": "255.255.255.0"
            },
            {
              "host_uuid": "1ef75076-9ac8-11f0-838d-1320f7e67d81",
              "service_interface_name": "port-storage",
              "service_interface_ip": "10.0.21.205",
              "netmask": "255.255.255.0"
            },
            {
              "host_uuid": "1f97a2d8-9ac8-11f0-978c-3b1611b8ef4a",
              "service_interface_name": "port-storage",
              "service_interface_ip": "10.0.21.206",
              "netmask": "255.255.255.0"
            }
          ]
        },
        "mode": {
          "type": "vlan_access",
          "network_identities": [
            0
          ]
        }
      }
    ],
    "hosts": [
      {
        "host_ip": "fe80::250:56ff:feb5:9440%ens192",
        "host_uuid": "1f967a52-9ac8-11f0-9b61-05cf1b7143e4",
        "hostname": "node-01",
        "disk_data_with_cache": False,
        "host_passwords": [
          {
            "user": "root",
            "password": "c+G6KvJYsKyQyY4U"
          },
          {
            "user": "smartx",
            "password": "c+G6KvJYsKyQyY4U"
          }
        ],
        "tags": [],
        "ifaces": [
          {
            "ip": "10.0.20.204",
            "function": "mgt"
          },
          {
            "ip": "10.0.21.204",
            "function": "storage"
          }
        ],
        "disks": [
          {
            "drive": "nvme0n1",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "nvme0n2",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "sdb",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "01000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdc",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "02000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdd",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "03000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sde",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "04000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdf",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "05000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          }
        ],
        "is_master": True,
        "with_faster_ssd_as_cache": True
      },
      {
        "host_ip": "fe80::e0a1:28ff:fecb:f5c3%ens192",
        "host_uuid": "1ef75076-9ac8-11f0-838d-1320f7e67d81",
        "hostname": "node-02",
        "disk_data_with_cache": False,
        "host_passwords": [
          {
            "user": "root",
            "password": "c+G6KvJYsKyQyY4U"
          },
          {
            "user": "smartx",
            "password": "c+G6KvJYsKyQyY4U"
          }
        ],
        "tags": [],
        "ifaces": [
          {
            "ip": "10.0.20.205",
            "function": "mgt"
          },
          {
            "ip": "10.0.21.205",
            "function": "storage"
          }
        ],
        "disks": [
          {
            "drive": "nvme0n1",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "nvme0n2",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "sdb",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "01000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdc",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "02000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdd",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "03000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sde",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "04000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdf",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "05000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          }
        ],
        "is_master": True,
        "with_faster_ssd_as_cache": True
      },
      {
        "host_ip": "fe80::9488:73ff:feeb:609%ens192",
        "host_uuid": "1f97a2d8-9ac8-11f0-978c-3b1611b8ef4a",
        "hostname": "node-03",
        "disk_data_with_cache": False,
        "host_passwords": [
          {
            "user": "root",
            "password": "c+G6KvJYsKyQyY4U"
          },
          {
            "user": "smartx",
            "password": "c+G6KvJYsKyQyY4U"
          }
        ],
        "tags": [],
        "ifaces": [
          {
            "ip": "10.0.20.206",
            "function": "mgt"
          },
          {
            "ip": "10.0.21.206",
            "function": "storage"
          }
        ],
        "disks": [
          {
            "drive": "nvme0n1",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "nvme0n2",
            "function": "cache",
            "model": "VMware Virtual NVMe Disk",
            "serial": "VMware NVME_0000",
            "size": 1759218604032,
            "type": "SSD"
          },
          {
            "drive": "sdb",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "01000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdc",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "02000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdd",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "03000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sde",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "04000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          },
          {
            "drive": "sdf",
            "function": "data",
            "model": "VMware_Virtual_SATA_Hard_Drive",
            "serial": "05000000000000000001",
            "size": 2199023255552,
            "type": "HDD"
          }
        ],
        "is_master": True,
        "with_faster_ssd_as_cache": True
      }
    ],
    "ntp": {
      "mode": "internal",
      "ntp_server": None,
      "current_time": "2025-09-26T14:13:44.255Z"
    },
    "vhost_enabled": True,
    "rdma_enabled": False
  })
  headers = {
    'host': host_ip,
    'content-type': 'application/json',
    'x-smartx-token': 'e79b85fc18b7402fbcc0391fe8d7d24c'
  }

  response = requests.request("POST", url, headers=headers, data=payload)

  print(response.text)

  ## 判断部署状态是否成功
  先通过GET请求，这个接口的host_ip参数是部署时传入的主机IP
  http://{host_ip}/api/v2/deployment/host/deploy_status?host_ip={host_ip}
  添加header
  x-smartx-token: e79b85fc18b7402fbcc0391fe8d7d24c

  返回示例中的state字段，如果为running，说明部署中，每隔十秒循环查询一次，当返回中状态不在含有running时（或者返回中含有error字段），说明部署过程结束，此时忽略该接口返回（因为可能会返回error或者其他非预期数据），使用下面的deploy_verify接口查询最终部署结果
  {
      "data": {
          "current_stage": 1,
          "msg": null,
          "stage_info": "prepare_network_and_config_file",
          "state": "running",
          "total_stages": 1
      },
      "ec": "EOK",
      "error": {}
  }

  当部署过程结束后，使用下面的接口查询最终部署结果
  GET请求
  https://{host_ip}/api/v2/deployment/deploy_verify
  添加header
  x-smartx-token: e79b85fc18b7402fbcc0391fe8d7d24c

  使用如上接口查询部署状态，返回示例如下，如果is_deployed为true，说明部署成功，如果为false，说明部署失败
  {
      "data": {
          "is_deployed": true,
          "platform": "kvm"
      },
      "ec": "EOK",
      "error": {}
  }


# 03-配置集群
  ## 部署后配置fisheye管理员密码

  请求网址
  https://10.0.20.211/api/v3/users:setupRoot
  请求方法
  POST

  host: 10.0.20.211
  content-type: application/json

  载荷 
  {"password":"HC!r0cks","repeat":"HC!r0cks","encrypted":false}

  ## 登录fisheye获取token
  请求网址
  https://10.0.20.211/api/v3/sessions
  请求方法
  POST
  载荷
  {"username":"root","password":"HC!r0cks","encrypted":false}

  响应示例
  {
      "user_id": "root",
      "token": "df91526d34a94dc9bada16437e1c579f",
      "create_time": "2025-09-27T22:38:57.921456349Z",
      "expire_time": "2025-10-04T22:38:57.921456419Z",
      "update_time": "2025-09-27T22:38:57.921456509Z"
  }
  其中token字段值即为后续调用接口需要的token值


  ## 部署后配置集群VIP

  请求网址
  https://10.0.20.211/api/v2/settings/vip
  请求方法
  PUT

  载荷
  {"iscsi_vip":null,"management_vip":"10.0.20.210"}

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  host：10.0.20.211
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  ## 部署后获取集群序列号
  请求网址
  https://10.0.20.211/api/v2/tools/license
  请求方法
  GET

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  host：10.0.20.211
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  响应示例
  {
    "ec": "EOK",
    "error": {},
    "data": {
      "serial": "c8b39907-464c-44b4-94bb-7c2ac243f390",
      "software_edition": "ENTERPRISE",
      "max_chunk_num": 255,
      "max_physical_data_capacity": 0,
      "max_physical_data_capacity_per_node": 140737488355328,
      "license_capabilities": {
        "has_metrox": true,
        "has_remote_backup": true
      },
      "license_type": "TRIAL",
      "vendor": "SMTX",
      "maintenance_start_date": 0,
      "maintenance_period": 0,
      "sign_date": 1759011131,
      "platform": 15,
      "mode": "HCI",
      "period": 2592000,
      "pricing_type": "PRICING_TYPE_UNKNOWN"
    }
  }

  ## 部署后配置dns
  前提要求是之前步骤已经获取到token
  PUT
  https://10.0.20.211​/api​/v2​/settings​/dns

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  host：10.0.20.211
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  载荷（根据规划表数量决定填写一个或者多个dns服务器地址，dns地址只能是IP结构）
  {"dns_servers":["10.0.0.114","10.0.0.1"]}


  返回示例
  {
    "ec": "EOK",
    "error": {},
    "data": {
      "job_id": "1fe85435-c402-4cf3-ab05-d161a7548757"
    }
  }


  ## 部署后配置ntp

  前提要求是之前步骤已经获取到token
  PUT
  ​https://10.0.20.211/api​/v2​/settings​/ntp

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  host：10.0.20.211
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  载荷（根据规划表数量决定填写一个或者多个ntp服务器地址，ntp服务器可能存在域名是正常的）
  {"ntp_mode":"external","ntp_servers":["10.0.0.2","ntp.c89.fun","10.0.0.1"]}

  返回示例
  {
    "ec": "EOK",
    "error": {},
    "data": {
      "job_id": "9d42fa9e-deab-448f-9b66-c956477d8457"
    }
  }

  ## 部署后配置IPMI信息
  前提要求是之前步骤已经获取到token
  请求网址
  https://10.0.20.210/api/v2/ipmi/upsert_accounts
  请求方法
  POST

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  请求主体
{"accounts":[{"node_name":"BJ-SMTX-Prod-Node-01","host":"10.0.1.11","user":"root","node_uuid":"6d977b4a-9ba7-11f0-b698-d935a246b994","password":"P@ssw0rd!123"},{"node_name":"BJ-SMTX-Prod-Node-02","host":"10.0.1.12","user":"root","node_uuid":"f6e8e2dc-9beb-11f0-a2f4-f96925dc8e16","password":"P@ssw0rd!123"},{"node_name":"BJ-SMTX-Prod-Node-03","host":"10.0.1.13","user":"root","node_uuid":"f80b760c-9beb-11f0-9564-1da72e84a9b8","password":"P@ssw0rd!123"}]}

  返回示例
{
  "ec": "EOK",
  "error": {},
  "data": {
    "success": [],
    "failure": [
      {
        "node_uuid": "6d977b4a-9ba7-11f0-b698-d935a246b994",
        "node_name": "BJ-SMTX-Prod-Node-01",
        "host": "10.0.1.11",
        "port": 623,
        "user": "root",
        "is_valid": false,
        "interface": null
      },
      {
        "node_uuid": "f6e8e2dc-9beb-11f0-a2f4-f96925dc8e16",
        "node_name": "BJ-SMTX-Prod-Node-02",
        "host": "10.0.1.12",
        "port": 623,
        "user": "root",
        "is_valid": false,
        "interface": null
      },
      {
        "node_uuid": "f80b760c-9beb-11f0-9564-1da72e84a9b8",
        "node_name": "BJ-SMTX-Prod-Node-03",
        "host": "10.0.1.13",
        "port": 623,
        "user": "root",
        "is_valid": false,
        "interface": null
      }
    ]
  }
}



  ## 创建业务虚拟交换机
请求网址
https://10.0.20.210/api/v2/network/vds
请求方法
POST

添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
x-smartx-token：d513e36581044eb691ba9589eebac995

请求主体（使用的nics_associated是规划表中业务网卡的名称，bond_mode是规划表中业务交换机的绑定模式，name是规划表中业务交换机的名称，data_ip是集群内主机的存储ip地址）
{"name":"vDS-Production","bond_mode":"active-backup","hosts_associated":[{"host_uuid":"6d977b4a-9ba7-11f0-b698-d935a246b994","nics_associated":["ens162","ens194"],"data_ip":"10.0.21.211"},{"host_uuid":"f6e8e2dc-9beb-11f0-a2f4-f96925dc8e16","nics_associated":["ens162","ens194"],"data_ip":"10.0.21.212"},{"host_uuid":"f80b760c-9beb-11f0-9564-1da72e84a9b8","nics_associated":["ens162","ens194"],"data_ip":"10.0.21.213"}]}

返回示例
{
  "ec": "EOK",
  "error": {},
  "data": {
    "job_id": "72bda4a1-0ca0-46dd-a44c-1393aba5d461"
  }
}

  ## 查询VDS创建状态
首先查询任务详情
请求网址（72bda4a1-0ca0-46dd-a44c-1393aba5d461是上一步创建VDS返回的job_id）
https://10.0.20.210/api/v2/jobs/72bda4a1-0ca0-46dd-a44c-1393aba5d461
请求方法
GET

添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
x-smartx-token：d513e36581044eb691ba9589eebac995

相应返回示例（示例中的"uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38",）
{
  "ec": "EOK",
  "error": {},
  "data": {
    "job": {
      "job_id": "72bda4a1-0ca0-46dd-a44c-1393aba5d461",
      "state": "pending",
      "life_cycle": "run",
      "description": "NETWORK_CREATE_VDS",
      "type": "action",
      "user": "",
      "resources": {
        "9f4aff8e-cb57-4d53-a874-ea8e326d5e38": {
          "type": "NETWORK_VDS",
          "uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38",
          "name": "vDS-Production",
          "ovsbr_name": "ovsbr-azpjnos8v",
          "description": "",
          "status": "created",
          "hosts_associated": {
            "6d977b4a-9ba7-11f0-b698-d935a246b994": {
              "host_uuid": "6d977b4a-9ba7-11f0-b698-d935a246b994",
              "nics_associated": [
                "ens162",
                "ens194"
              ],
              "data_ip": "10.0.21.211"
            },
            "f6e8e2dc-9beb-11f0-a2f4-f96925dc8e16": {
              "host_uuid": "f6e8e2dc-9beb-11f0-a2f4-f96925dc8e16",
              "nics_associated": [
                "ens162",
                "ens194"
              ],
              "data_ip": "10.0.21.212"
            },
            "f80b760c-9beb-11f0-9564-1da72e84a9b8": {
              "host_uuid": "f80b760c-9beb-11f0-9564-1da72e84a9b8",
              "nics_associated": [
                "ens162",
                "ens194"
              ],
              "data_ip": "10.0.21.213"
            }
          },
          "bond_name": "bond-m-9f4aff8e",
          "bond_type": "ovs_bond",
          "bond_mode": "active-backup",
          "work_mode": "single",
          "qos_enable": false,
          "rb_interval": ""
        }
      },
      "schedule_task": null,
      "one_time_task": null,
      "ctime": 1759072687,
      "task_list": [],
      "queue": null,
      "resource_group": null,
      "event": {
        "event_name": "CREATE_VDS",
        "user_name": "root",
        "user_role": "ROOT",
        "resources": {
          "9f4aff8e-cb57-4d53-a874-ea8e326d5e38": "NETWORK_VDS"
        },
        "message": {
          "zh_CN": "\u521b\u5efa\u865a\u62df\u5206\u5e03\u5f0f\u4ea4\u6362\u673a vDS-Production\u3002\n",
          "en_US": "Created virtual distributed switch vDS-Production.\n"
        },
        "detail": {
          "zh_CN": "\u521b\u5efa: \n\u865a\u62df\u5206\u5e03\u5f0f\u4ea4\u6362\u673a\u540d: vDS-Production\n\u7f51\u53e3\u7ed1\u5b9a\u6a21\u5f0f: active-backup\n\u6e90\u8d1f\u8f7d\u5e73\u8861\u7ed1\u5b9a\u5e73\u8861\u95f4\u9694: -\n\u5173\u8054\u7f51\u53e3: \n    BJ-SMTX-Prod-Node-01: ens162, ens194\n    BJ-SMTX-Prod-Node-02: ens162, ens194\n    BJ-SMTX-Prod-Node-03: ens162, ens194\n",
          "en_US": "Created: \nVDS name: vDS-Production\nbonding: active-backup\nslb rebalance interval: -\nAssociated NICs: \n    BJ-SMTX-Prod-Node-01: ens162, ens194\n    BJ-SMTX-Prod-Node-02: ens162, ens194\n    BJ-SMTX-Prod-Node-03: ens162, ens194\n"
        },
        "data": {
          "name": "vDS-Production",
          "uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38"
        },
        "user_type": "USER",
        "batch": null
      }
    }
  }
}


拿到VDS的uuid后，使用下面的接口查询VDS详情，确认VDS创建成功

请求网址（9f4aff8e-cb57-4d53-a874-ea8e326d5e38是上一步创建的VDS的uuid）
https://10.0.20.210/api/v2/network/vds/9f4aff8e-cb57-4d53-a874-ea8e326d5e38
请求方法
GET

添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
x-smartx-token：d513e36581044eb691ba9589eebac995

返回示例（确认bond_mode，name，hosts_associated等信息正确）
{
  "ec": "EOK",
  "error": {},
  "data": {
    "uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38",
    "bond_mode": "active-backup",
    "bond_name": "bond-m-9f4aff8e",
    "bond_type": "ovs_bond",
    "description": "",
    "name": "vDS-Production",
    "ovsbr_name": "ovsbr-azpjnos8v",
    "qos_enable": false,
    "rb_interval": "",
    "type": 1,
    "work_mode": "single",
    "hosts_associated": [],
    "vlans_count": 0
  }
}

  ## 创建业务网络
创建并查询VDS正确创建之后，使用下面的接口创建业务网络
请求网址（9f4aff8e-cb57-4d53-a874-ea8e326d5e38是上一步创建的VDS的uuid）
https://10.0.20.210/api/v2/network/vds/9f4aff8e-cb57-4d53-a874-ea8e326d5e38/vlans
请求方法
POST

添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
x-smartx-token：d513e36581044eb691ba9589eebac995

请求主体（name是规划表中业务网络名称，vlan_id是规划表中业务网络VLAN ID，vds_uuid是上一步创建的VDS的uuid）
规划表中可能存在多个业务网络，根据规划表中业务网络数量，循环创建多个业务网络，每个请求主体中只包含一个业务网络
{"name":"VLAN-1120","vlan_id":1120,"vds_uuid":"9f4aff8e-cb57-4d53-a874-ea8e326d5e38"}

返回示例
{
  "ec": "EOK",
  "error": {},
  "data": {
    "uuid": "dc819658-ce2e-4996-8d97-38da03e6f95f",
    "name": "VLAN-1120",
    "vds_uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38",
    "vlan_id": 1120,
    "type": 3,
    "enable_dhcp": false,
    "vms_count": 0,
    "vm_snapshots_count": 0,
    "vm_templates_count": 0,
    "dhcp_config": null
  }
}

当所有业务网络创建完成后，再使用下面的接口查询该VDS下的业务网络数量，确认业务网络创建成功
请求网址（9f4aff8e-cb57-4d53-a874-ea8e326d5e38是上一步创建的VDS的uuid）
https://10.0.20.210/api/v2/network/vds/9f4aff8e-cb57-4d53-a874-ea8e326d5e38
请求方法
GET

添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
x-smartx-token：d513e36581044eb691ba9589eebac995

返回示例（"vlans_count": 0中的数字是业务网络的数量，确认与规划表中业务网络数量一致）
{
  "ec": "EOK",
  "error": {},
  "data": {
    "uuid": "9f4aff8e-cb57-4d53-a874-ea8e326d5e38",
    "bond_mode": "active-backup",
    "bond_name": "bond-m-9f4aff8e",
    "bond_type": "ovs_bond",
    "description": "",
    "name": "vDS-Production",
    "ovsbr_name": "ovsbr-azpjnos8v",
    "qos_enable": false,
    "rb_interval": "",
    "type": 1,
    "work_mode": "single",
    "hosts_associated": [],
    "vlans_count": 0
  }
}


  ## 批量配置主机密码（root和smartx账号）
  通过使用smartx账号（初始化集群后的默认密码是P@ssw0rd!123，需要修改为规划表中的密码）ssh到主机执行passwd命令实现
  根据规划表中的密码对主机密码进行批量修改

  ## 上传虚拟机工具（SVT）（还未完成，等待接口文档）
  通过接口首先创建SVT卷
  请求网址（两个参数，name是上传的文件名称，size是上传的文件大小，单位是字节）
  https://10.0.20.211/api/v2/svt_image/create_volume?name=SMTX_VMTOOLS-3.2.0-2501210639.iso&size=317816832
  请求方法
  POST

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  返回响应
  返回码200
  并且服务端会返回一个 volume 对象，里面带了 chunk_size、zbs_volume_id、image_uuid 等信息。
  其中 chunk_size 是每次上传的块大小，zbs_volume_id 是上传卷的 ID，image_uuid 是上传的镜像 UUID。
  这两个 ID 后续上传二进制文件时需要使用。
  to_upload是总共需要切片的数量，chunkIdx 初始化为 0
  {
      "data": {
          "chunk_size": 8388608,
          "image_path": "/usr/share/smartx/images/vmtools/4f6bff6e-2ede-479a-a48c-98ea95329961",
          "image_uuid": "4f6bff6e-2ede-479a-a48c-98ea95329961",
          "to_upload": [
              0,
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20,
              21,
              22,
              23,
              24,
              25,
              26,
              27,
              28,
              29,
              30,
              31,
              32,
              33,
              34,
              35,
              36,
              37
          ],
          "zbs_volume_id": "5660a816-a50d-4bcf-b112-ab9ba9075548"
      },
      "ec": "EOK",
      "error": {}
  }


  第二阶段是将文件上传到SVT卷中，通过二进制方式上传
  示例如下

  请求网址（三个参数，zbs_volume_id是上一步创建上传卷返回的zbs_volume_id，chunk_num是当前上传的块编号，从0开始递增，image_uuid是上一步创建上传卷返回的image_uuid）
  https://10.0.20.211/api/v2/svt_image/upload_template?zbs_volume_id=c9b614f9-4a95-4f1d-8d3a-914296941dab&chunk_num=0&image_uuid=7e97e211-e6b4-4f65-a72b-8b767d2c85ab
  请求方法
  POST

  header（这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  请求 Body
  类型应该为表单（内容是二进制数据）  multipart/form-data
  将指定文件按 chunk_size 大小分块上传，chunk_num 从 0 开始递增，直到文件上传完成。


  状态代码 200




# 04-部署cloudtower并配置

  ## 上传cloudtower ISO

  ### 检查是否已经存在iso

  请求方法
  GET
  请求网址
  /api/v2/images

  header
  host：10.0.20.210（是api请求的主机地址）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  响应示例（如果已经存在相同名称和大小的ISO文件，则不需要重复上传） 

  {
  "data": {
    "images": [
      {
        "description": "cloudtower os image",
        "file_name": "6b6bf01d-683c-4e9a-acbd-aabee55a81d3",
        "md5": "6a3f073bc1094a3bc55963761a574f6d",
        "name": "cloudtower-v4.6.2.oe2003.x86_64.iso",
        "os": null,
        "path": "iscsi://iqn.2016-02.com.smartx:system:zbs-iscsi-datastore-6d4a5daf-974e-4a4d-b185-805525ca1385/129",
        "resource_state": "in-use",
        "size": 7952123904,
        "time": 1761667095,
        "type": "ISO_IMAGE",
        "uuid": "6b6bf01d-683c-4e9a-acbd-aabee55a81d3",
        "vm_snapshots_count": 0,
        "vm_templates_count": 0,
        "vms_count": 0,
        "zbs_volume_id": "a6dd47d1-44d2-48e7-9799-ee42ac3a1452"
      }
    ]
  },
  "ec": "EOK",
  "error": {}
}



  ### 第一步先创建上传卷
  
  接口
  POST
  https://10.0.20.211/api/v2/images/upload/volume?description=&name=cloudtower-v4.6.2.oe2003.x86_64&device=nfs&task_id=1&size=7873968128

  参数
  name 是文件名称
  size 是文件大小，单位是字节
  description 是文件描述，可以为空
  device 是上传卷的存储类型，只支持 nfs
  task_id 是任务 ID，固定为2


  header
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  返回示例（image_uuid和zbs_volume_id后续上传二进制时需要使用；to_upload是要上传的分片数量，这个随着后续每次上传调用会不断增加直到为空值时意味着上传结束；chunk_size是后续每个chunk分片的二进制大小）
  "image_path"字段是上传卷的路径，后续创建虚拟机时挂载ISO需要使用
  {
      "data": {
          "chunk_size": 8388608,
          "image_path": "iscsi://iqn.2016-02.com.smartx:system:zbs-iscsi-datastore-d287eb4f-90e5-444a-a50c-37d69b232200/67",
          "image_uuid": "b75f7429-5a4c-428f-b506-3deb3fdbe54d",
          "to_upload": [
              0,
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              ** 数字是依次增大的，为了节省文档空间，这里省略了很多行 **
              929,
              930,
              931,
              932,
              933,
              934,
              935,
              936,
              937,
              938
          ],
          "zbs_volume_id": "a54485ed-c1d0-4e00-916a-ef70fabbaa6f"
      },
      "ec": "EOK",
      "error": null
  }

  ### 第二步上传ISO文件二进制文件到上传卷

  POST
  ​/api​/v2​/images​/upload

  参数
  zbs_volume_id *必须
  string
  (query)
  ZBS 卷 ID。

  chunk_num *必须
  number
  (query)
  块（chunk）数。

  image_uuid *必须
  string
  (query)
  虚拟卷的 UUID。

  请求 Body（根据第一步的chunk_size分块上传，chunkIdx 初始化为 0，to_upload意味着还有多少个分片还需要上传，chunk_num数量会在后续上传中不断增加，每次上传时需要将chunk_num作为参数传入）

  multipart/form-data
  file *
  string($binary)

  返回（如果该分片上传失败，重试2次，如果还是失败，终止上传并删除该上传卷，重新创建上传卷并上传（重试一次））
  {
    "ec": "EOK",
    "error": {},
    "data": {
      "chunk_num": 0,
      "to_upload": [
        0
      ]
    }
  }

  ### 如果上传过程中出现错误，可以调用下面的接口删除上传卷
  DELETE
  ​/api​/v2​/images​/{image_uuid}

  删除一个映像

  参数
  名称	描述
  image_uuid *必须
  string
  (path)
  映像的 UUID。

  返回值
  状态码
  200	



  ## 创建cloudtower虚拟机并挂载ISO
  请求网址
  https://10.0.20.211/api/v2/vms
  请求方法
  POST

  header
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  请求载荷说明
  vm_name是虚拟机名称，来源规划表
  description是虚拟机描述，固定为CloudTower VM auto created by CXVoyager
  vcpu是虚拟机CPU数量，固定为8
  memory是虚拟机内存大小，单位是字节，固定为20401094656
  cpu.topology.sockets是虚拟机CPU插槽数量，固定为8
  cpu.topology.cores是每个插槽的核心数，固定为1
  nics是虚拟机网卡信息，ovs是管理交换机的ovs名称，需要使用api查询
  model是网卡模型，固定为virtio，
  mirror是是否镜像，固定为false，
  vlan_uuid是管理网络UUID，通过api进行查询
  link是网卡连接状态，固定为up
  disks是虚拟机磁盘信息
  type是磁盘类型，os磁盘固定为disk，光驱固定为cdrom
  bus是磁盘总线类型，os磁盘固定为virtio，光驱固定为ide
  storage_policy_uuid是存储策略UUID，通过api进行查询
  name是磁盘名称，os磁盘固定为cloudtower-os
  quota_policy是配额策略，固定为null
  size_in_byte是磁盘大小，os磁盘固定为429496729600
  path是光驱挂载路径，来源第一步上传cloudtower ISO时返回的image_path
  disabled是光驱是否禁用，固定为false
  ha是是否开启高可用，固定为true
  nested_virtualization是是否开启嵌套虚拟化，固定为false
  cpu_model是CPU模型，固定为cluster_default
  firmware是固件类型，固定为BIOS
  diskNamePrefix是磁盘名称前缀，固定为cloudtower
  auto_schedule是是否自动调度，固定为true
  status是虚拟机状态，固定为running
  其他参数保持示例值不变    

载荷示例
{
    "vm_name": "cloudtower",
    "description": "CloudTower VM auto created by CXVoyager",
    "vcpu": 8,
    "memory": 20401094656,
    "cpu": {
        "topology": {
            "sockets": 8,
            "cores": 1
        }
    },
    "nics": [
        {
            "ovs": "ovsbr-ef58xhlz0",
            "model": "virtio",
            "mirror": false,
            "vlan_uuid": "c8a1e42d-e0f3-4d50-a190-53209a98f157",
            "link": "up"
        }
    ],
    "disks": [
        {
            "type": "disk",
            "bus": "virtio",
            "storage_policy_uuid": "dce52578-3824-4b34-97a2-af09950bb0ac",
            "name": "cloudtower-os",
            "quota_policy": null,
            "size_in_byte": 429496729600
        },
        {
            "type": "cdrom",
            "bus": "ide",
            "path": "iscsi://iqn.2016-02.com.smartx:system:zbs-iscsi-datastore-85bc902a-996d-4618-a556-67f40e2f5e6f/86",
            "disabled": false
        }
    ],
    "ha": true,
    "nested_virtualization": false,
    "hasNormalVol": false,
    "hasSharedVol": false,
    "hasVolume": false,
    "cpu_model": "cluster_default",
    "firmware": "BIOS",
    "diskNamePrefix": "cloudtower",
    "folder_uuid": null,
    "node_ip": null,
    "auto_schedule": true,
    "existDisks": [],
    "quota_policy": null,
    "status": "running"
}

返回
{
  "data": {
    "job_id": "956aacfc-8e0c-4d02-9cd6-9628825aea32"
  },
  "ec": "EOK",
  "error": {}
}

  ### 查询cloudtower虚拟机创建状态
  请求网址（956aacfc-8e0c-4d02-9cd6-9628825aea32是上一步创建cloudtower虚拟机返回的job_id）
  GET
  ​/api​/v2​/jobs​/{job_id}

  返回示例（state字段为done表示创建成功，resources字段中包含了虚拟机的详细信息，包括后续需要使用的UUID）
  {
    "ec": "EOK",
    "error": {},
    "data": {
        "job": {
            "job_id": "956aacfc-8e0c-4d02-9cd6-9628825aea32",
            "state": "done",
            "life_cycle": "run",
            "description": "VM_CREATE",
            "type": "action",
            "user": "",
            "resources": {
                "e6b88b9e-6d20-490b-b16b-09105c2cc086": {
                    "uuid": "e6b88b9e-6d20-490b-b16b-09105c2cc086",
                    "vm_name": "cloudtower",
                    "vcpu": 8,
                    "cpu": {
                        "topology": {
                            "sockets": 8,
                            "cores": 1
                  …………中间省略其他内容
                        } 
                    }
                }
            }
        }
    }
}


  ## 启动cloudtower虚拟机并安装操作系统
  创建虚拟机后，由于设置了status为running，虚拟机会自动启动，
  cloudtower iso内部使用kickstart脚本实现操作系统自动安装，只需要等待cloudtower安装完成即可

  ## 判断cloudtower虚拟机操作系统是否安装完成
  通过查询虚拟机状态，识别svt vmtools是否正在运行，判断操作系统是否正确安装并引导

  GET
  /api/v2/vms/{vm_uuid}
  （vm_uuid是上一步创建cloudtower虚拟机时返回的虚拟机UUID）

  header
  x-smartx-token：df91526d34a94dc9bada16437e1c579f
  host：10.0.20.210

  响应示例（检测到cloudtower虚拟机的"guest_os_type": 不为unknown（预期为含有openeuler 或centos类似名称），而且"ga_state": "Running",表示svt vmtools正在运行，操作系统和svt agent安装成功）
  {
  "data": {
    "auto_schedule": true,
    "bios_uuid": "a2e4df2e-255e-43e9-8198-9f7c9e15404b",
    "boot_with_host": false,
    "clock_offset": "utc",
    "cloud_init_supported": false,
    "cluster_cpu_model": "host_passthrough",
    "cpu": {
      "topology": {
        "cores": 1,
        "sockets": 8
      }
    },
    "cpu_exclusive": {
      "actual_enabled": false,
      "expected_enabled": false
    },
    "cpu_model": "cluster_default",
    "cpu_qos": {
      "limit_hz": -1,
      "reservation_hz": 0,
      "shares": 1000
    },
    "create_time": 1761675370,
    "description": "CloudTower VM auto created by CXVoyager",
    "disks": [
      {
        "boot": 1,
        "bus": "virtio",
        "encryption_algorithm": "PLAINTEXT",
        "name": "cloudtower-os",
        "path": "iscsi://iqn.2016-02.com.smartx:system:zbs-iscsi-datastore-9b2a4a18-855b-49f7-83bc-ed9df3cdbb89/206",
        "quota_policy": null,
        "resident_in_cache": false,
        "resident_in_cache_percentage": 0,
        "serial": "97473404-ed89-3b50-9e43-4a7e662b9960",
        "size": 429496729600,
        "storage_policy_uuid": "dce52578-3824-4b34-97a2-af09950bb0ac",
        "type": "disk",
        "volume_is_sharing": false,
        "volume_uuid": "ac1ed08e-d06e-40c2-af9a-d2a3d47796e0"
      },
      {
        "boot": 2,
        "bus": "ide",
        "disabled": false,
        "key": 100,
        "path": "iscsi://iqn.2016-02.com.smartx:system:zbs-iscsi-datastore-6d4a5daf-974e-4a4d-b185-805525ca1385/225",
        "quota_policy": null,
        "storage_policy_uuid": null,
        "type": "cdrom"
      }
    ],
    "firmware": "BIOS",
    "guest_cpu_model": "host_passthrough",
    "guest_info": {
      "dns_servers": [],
      "expired": false,
      "ga_state": "Running",
      "ga_version": 4000000,
      "gateway_ips": [
        "::"
      ],
      "hostname": "localhost.localdomain",
      "kernel_info": "4.19.90-2307.3.0.oe1.smartx.37.x86_64",
      "mounted": false,
      "nics": [
        {
          "gateway_ip": "",
          "gateway_ip_v6": "::",
          "hardware_address": "00:00:00:00:00:00",
          "ip_addresses": [
            {
              "ip_address": "127.0.0.1",
              "ip_address_type": "ipv4",
              "netmask": "255.0.0.0",
              "prefix": "8"
            },
            {
              "ip_address": "::1",
              "ip_address_type": "ipv6",
              "netmask": "",
              "prefix": "128"
            }
          ],
          "ip_type": "unknown",
          "ip_type_v6": "unknown",
          "name": "lo"
        },
        {
          "gateway_ip": "",
          "gateway_ip_v6": "",
          "hardware_address": "52:54:00:74:c3:98",
          "ip_addresses": [],
          "ip_type": "dhcp",
          "ip_type_v6": "dhcp",
          "name": "ens4"
        }
      ],
      "os_version": "openEuler 20.03 (LTS-SP3)",
      "storage": {
        "disks": [
          {
            "name": "/dev/vda",
            "serial": "095936e3-b411-4c94-a",
            "size": 429496729600,
            "used": null
          }
        ],
        "mount_points": [
          {
            "path": "/boot",
            "size": 466569216,
            "type": "ext4",
            "used": 128922624
          },
          {
            "path": "/",
            "size": 399619276800,
            "type": "ext4",
            "used": 8683937792
          }
        ],
        "size": 429496729600,
        "storage_pools": [],
        "used": null
      },
      "update_time": 1761676258,
      "vip": null
    },
    "guest_os_type": "unknown",
    "ha": true,
    "ha_priority": 500,
    "hostdevs": [],
    "internal": false,
    "last_shutdown_time": 1761675370,
    "last_start_time": 1761675379,
    "memory": 20401094656,
    "nested_virtualization": false,
    "nics": [
      {
        "gateway": "",
        "interface_id": "3f135af5-74fe-44f8-b495-4a212ab8e833",
        "link": "up",
        "mac_address": "52:54:00:74:c3:98",
        "mirror": false,
        "model": "virtio",
        "ovs": "ovsbr-3wzp94is6",
        "ovs_health_status": "healthy",
        "pci_address": "0000:00:04.0",
        "queues": 8,
        "type": "VLAN",
        "vlan_uuid": "c8a1e42d-e0f3-4d50-a190-53209a98f157",
        "vlans": [
          {
            "enable_dhcp": null,
            "mode_type": "vlan_access",
            "mtu": null,
            "name": "default",
            "type": 3,
            "uuid": "c8a1e42d-e0f3-4d50-a190-53209a98f157",
            "vds_uuid": "db7f4eba-1f5e-4366-8e12-166493097dea",
            "vlan_id": 0
          }
        ]
      }
    ],
    "node_ip": "10.0.21.12",
    "placement_groups": [],
    "quota_policy": null,
    "resource_state": "in-use",
    "status": "running",
    "svt_iso": "",
    "sync_vm_time_on_resume": false,
    "type": "KVM_VM",
    "update_time": 1761675379,
    "uptime": 947,
    "uuid": "f841747c-344d-4091-8c7f-030da10c14b4",
    "vcpu": 8,
    "video_type": "cirrus",
    "vm_name": "cloudtower",
    "vm_version": "elf-1.2",
    "vm_version_mode": "vm-version-auto",
    "win_opt": null
  },
  "ec": "EOK",
  "error": {}
}


  ## 通过vmtools配置cloudtower网络
  在上一步确认操作系统安装成功后，使用下面的接口配置cloudtower虚拟机网络信息

  请求网址（e6b88b9e-6d20-490b-b16b-09105c2cc086是创建cloudtower虚拟机返回的虚拟机uuid）
  PUT
  ​/api/v2/vms/{vm_uuid}

  header  
  host：10.0.20.210（是api请求的主机地址）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  请求载荷
  nics是网卡信息，
  vlan_uuid是管理网络UUID，通过api进行查询，
  ovs是管理交换机的ovs名称，需要使用api查询，
  model是网卡模型，固定为virtio，
  mac_address是虚拟机网卡MAC地址，可以通过查询虚拟机详情获取，
  mirror是是否镜像，固定为false，
  gateway是网关地址，来源规划表，
  subnet_mask是子网掩码，来源规划表，
  ip_address是虚拟机IP地址，来源规划表，
  link是网卡连接状态，固定为up
  {
    "nics": [
        {
            "vlan_uuid": "c8a1e42d-e0f3-4d50-a190-53209a98f157",
            "ovs": "ovsbr-ef58xhlz0",
            "model": "virtio",
            "mac_address": "52:54:00:bc:dc:79",
            "mirror": false,
            "gateway": "10.0.20.1",
            "subnet_mask": "255.255.255.0",
            "ip_address": "10.0.20.220",
            "link": "up"
        }
    ]
  }

  返回示例
  {
      "data": {
          "job_id": "3cce4788-f5d2-4424-ab96-a024a8d7bc86"
      },
      "ec": "EOK",
      "error": {}
  }

  ## 查询cloudtower虚拟机网络配置状态
  请求网址
  通过上一步返回的job_id查询任务状态
  GET
  ​/api​/v2​/jobs​/{job_id}
  返回示例（state字段为done表示网络配置成功）
  

  ## 通过ssh执行cloudtower服务部署脚本
  cloudtower虚拟机网络配置任务成功完成后，尝试通过ssh连接cloudtower虚拟机，执行部署脚本

  ssh连接使用cloudtower账号，密码是默认的HC!r0cks，这个是固定密码

  执行以下命令进行部署
  sudo sh /usr/share/smartx/tower/preinstall.sh && sudo nohup sudo /usr/share/smartx/tower/installer/binary/installer deploy &
  这个部署过程大概需要20分钟左右，期间会有大量日志输出，可以通过
  sudo tail -f nohup.out日志文件来监控部署进度
  当日志中出现 Install Operation Center Successfully 字样时，表示部署成功


  ## 等待cloudtower服务部署完成并验证
  部署完毕后检测443端口是否可以访问，如果可以访问，说明cloudtower部署成功，可以进行后续配置。
  如果不能访问，等待10秒后再次检测，重试三次，如果还是不能访问，说明cloudtower部署失败，抛出错误并终止程序运行

  ## 配置cloudtower 管理员密码
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  载荷（root_password是cloudtower管理员密码，此处"root_password":"NzllNTE3NTgxYWY5NDY3ODM4ZTczMTg1MDc4YmM3YzQ6eVpSSTlodUNxNDBNL3J4ZTViZ1dqZz09"是硬编码，默认密码就是HC!r0cks，不能修改；now是当前时间，格式为2025-09-30T18:42:47.920Z）
  {"operationName":"createRootUser","variables":{"root_password":"NzllNTE3NTgxYWY5NDY3ODM4ZTczMTg1MDc4YmM3YzQ6eVpSSTlodUNxNDBNL3J4ZTViZ1dqZz09","now":"2025-09-30T18:42:47.920Z"},"query":"mutation createRootUser($root_password: String!, $now: DateTime!) {\n  createUser(data: {name: \"root\", source: LOCAL, role: ROOT, username: \"root\", display_username: \"root\", password: $root_password, password_recover_qa: {enabled: false, items: []}, password_updated_at: $now}, effect: {encoded: true}) {\n    id\n    __typename\n  }\n}\n"}

  响应示例
  {"data":{"createUser":{"id":"cmg6wngqb037g09586kbpoj03","__typename":"User"}}}

  ## 配置cloudtower 组织名称
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  载荷（八九实验室是组织名称，来源规划表）
  {"operationName":"createOrganization","variables":{"data":{"name":"八九实验室"}},"query":"mutation createOrganization($data: OrganizationCreateInput!) {\n  createOrganization(data: $data) {\n    id\n    __typename\n  }\n}\n"}

  响应示例（id字段是创建的组织UUID，后续创建数据中心时会使用）
  {
      "data": {
          "createOrganization": {
              "id": "cmg6wngpq03790958j39dbd3v",
              "__typename": "Organization"
          }
      }
  }

  ## 验证cloudtower 管理员密码和组织名称配置成功
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  载荷
  {"operationName":"checkTowerIsSetup","variables":{},"query":"query checkTowerIsSetup {\n  organizations(first: 1) {\n    id\n    name\n    __typename\n  }\n  userCreated {\n    created\n    __typename\n  }\n}\n"}

  响应示例（organizations字段中包含了上一步创建的组织名称，userCreated.created字段为true表示管理员密码创建成功）
  {
      "data": {
          "organizations": [
              {
                  "id": "cmg6wngpq03790958j39dbd3v",
                  "name": "八九实验室",
                  "__typename": "Organization"
              }
          ],
          "userCreated": {
              "created": true,
              "__typename": "UserCreatedData"
          }
      }
  }

  ## 登录cloudtower 获取token
  请求网址
  http://CLOUDTOWER_IP/v2/api/login
  请求方法
  POST

  载荷（硬编码，不需要修改）
  {
  "username": "root",
  "source": "LOCAL",
  "password": "HC!r0cks"
  }

  返回示例
  {
      "data": {
          "token": "eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04"
      },
      "task_id": null
  }


  ## 配置cloudtower ntp
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（ntp_service_url是NTP服务器地址，多个地址使用逗号分隔，来源规划表）
  {"operationName":"updateCloudTowerNtpUrl","variables":{"data":{"ntp_service_url":"10.0.0.2,ntp.c89.fun,10.0.0.1"}},"query":"mutation updateCloudTowerNtpUrl($data: NtpCommonUpdateInput!) {\n  updateCloudTowerNtpUrl(data: $data) {\n    ntp_service_url\n    __typename\n  }\n}\n"}

  响应示例
  {
      "data": {
          "updateCloudTowerNtpUrl": {
              "ntp_service_url": "10.0.0.2;ntp.c89.fun;10.0.0.1",
              "__typename": "UpdateNtpCommonResult"
          }
      }
  }

  ## 配置cloudtower dns
  通过ssh到cloudtower虚拟机，修改 /etc/resolv.conf 文件，添加DNS服务器地址，来源规划表

  ## 导出cloudtower 序列号写入规划表
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷
  {"operationName":"deployedLicense","variables":{},"query":"query deployedLicense {\n  deploys(first: 1) {\n    id\n    license {\n      id\n      license_serial\n      maintenance_end_date\n      maintenance_start_date\n      max_chunk_num\n      max_cluster_num\n      max_vm_num\n      used_vm_num\n      sign_date\n      expire_date\n      software_edition\n      type\n      vendor\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应（license_serial字段是cloudtower序列号，写入规划表）
  {
      "data": {
          "deploys": [
              {
                  "id": "dac36138-22d1-4a67-a386-0d3625b5c824",
                  "license": {
                      "id": "cmg6w7xh700i00958zr2o63tf",
                      "license_serial": "e977a0ae-0bc6-4da4-a869-3724a232f3d7",
                      "maintenance_end_date": null,
                      "maintenance_start_date": null,
                      "max_chunk_num": 0,
                      "max_cluster_num": 0,
                      "max_vm_num": 0,
                      "used_vm_num": 0,
                      "sign_date": "2025-09-30T18:30:42.192Z",
                      "expire_date": "2025-12-29T18:30:42.192Z",
                      "software_edition": "ENTERPRISE",
                      "type": "TRIAL",
                      "vendor": "SMTX",
                      "__typename": "License"
                  },
                  "__typename": "Deploy"
              }
          ]
      }
  }

# 05-关联cloudtower并配置集群

  ## 获取组织ID
  在创建数据中心时需要使用组织ID，使用下面的接口查询组织ID
  /v2/api/get-organizations

  header头部
  Authorization：eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  返回示例（id字段是组织ID，后续创建数据中心时会使用）
  {
    "datacenters": [
      {
        "id": "string",
        "name": "string"
      }
    ],
    "id": "string",
    "name": "string"
  }


  ## 创建数据中心

  方法
  post
  入口
  https://10.0.20.220/v2/api/create-datacenter

  header头部
  Authorization：eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（organization_id是上一步创建组织时返回的ID；name是数据中心名称，来源规划表）
  {
  "organization_id": "ck74rk21wg5lz0786opdnzz5m",
  "name": "name-string"
  }

  返回示例（data.id是数据中心ID，后续关联集群时会使用）

  {
      "data": {
          "id": "cmg6xwkic04yr0958umaugrg8",
          "name": "八九实验室",
          "cluster_num": 0,
          "host_num": 0,
          "vm_num": 0,
          "total_data_capacity": null,
          "used_data_space": null,
          "failure_data_space": null,
          "total_cpu_hz": null,
          "used_cpu_hz": null,
          "total_memory_bytes": null,
          "used_memory_bytes": null,
          "organization": {
              "id": "cmg6wngpq03790958j39dbd3v",
              "name": "C89"
          },
          "clusters": [],
          "labels": []
      },
      "task_id": null
  }



  ## 关联集群
  方法
  post
  
  API入口
  https://10.0.20.220/v2/api/connect-cluster

  header头部
  Authorization：eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（datacenter_id是数据中心ID，上一步创建数据中心后获取；ip是集群VIP；username是集群登录用户名固定为root；password是集群登录密码，来源规划表）
  {
  "datacenter_id": "cmg6xwkic04yr0958umaugrg8",
  "password": "HC!r0cks",
  "username": "root",
  "ip": "10.0.20.210"
  }

  返回示例（返回集群ID，后续配置集群时会使用）
  {
      "data": {
          "id": "cmg6y13w6055h0958o1afczt5",
          "name": "CN-BJ-SMTX-Prod-Cls01",
          "hypervisor": "ELF",
          "version": "6.2.0",
          "architecture": "X86_64",
          "connect_state": "INITIALIZING",
          "dns": [],
          "ip": "10.0.20.210",
          "ntp_servers": [],
          "recommended_cpu_models": [],
          "total_cpu_models": [],
          "type": "SMTX_OS",
          "labels": []
      },
      "task_id": "cmg6y13ww010b7uud16oscy1g"
  }

  ## 验证集群关联状态
  方法post
  入口
  https://10.0.20.220/v2/api/get-clusters

  添加header头部
  authorization：eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  响应返回 （确认集群connect_state字段为CONNECTED，表示集群关联成功）
  {
      "application_highest_version": "6.2.0",
      "applications": [],
      "architecture": "X86_64",
      "auto_converge": true,
      "connect_state": "CONNECTED",
      "consistency_groups": [],
      "current_cpu_model": "host_passthrough",
      "datacenters": [
          {
              "id": "cmg6xwkic04yr0958umaugrg8",
              "name": "八九实验室"
          }
      ],
      "disconnected_date": null,
      "disconnected_reason": null,
      "dns": [
          "10.0.0.114",
          "10.0.0.1"
      ],
      "entityAsyncStatus": null,
      "everoute_cluster": null,
      "failure_data_space": 0,
      "has_metrox": true,
      "host_num": 3,
      "hosts": [
          {
              "id": "cmg6y152005sd0958816monwm",
              "management_ip": "10.0.20.211",
              "name": "BJ-SMTX-Prod-Node-01"
          },
          {
              "id": "cmg6y152005se0958azn950vg",
              "management_ip": "10.0.20.213",
              "name": "BJ-SMTX-Prod-Node-03"
          },
          {
              "id": "cmg6y152105sf0958kpamnaq1",
              "management_ip": "10.0.20.212",
              "name": "BJ-SMTX-Prod-Node-02"
          }
      ],
      "hypervisor": "ELF",
      "id": "cmg6y13w6055h0958o1afczt5",
      "ip": "10.0.20.210",
      "is_all_flash": false,
      "iscsi_vip": null,
      "labels": [],
      "license_expire_date": "2025-10-30T08:57:09.000Z",
      "license_serial": "30724c9c-9657-46af-9c55-3857c8f165c1",
      "license_sign_date": "2025-09-30T08:57:09.000Z",
      "license_type": "TRIAL",
      "local_id": "30724c9c-9657-46af-9c55-3857c8f165c1",
      "maintenance_end_date": "1970-01-01T00:00:00.000Z",
      "maintenance_start_date": "1970-01-01T00:00:00.000Z",
      "management_vip": "10.0.20.210",
      "max_chunk_num": 255,
      "max_physical_data_capacity": 0,
      "max_physical_data_capacity_per_node": 140737488355328,
      "metro_availability_checklist": null,
      "mgt_gateway": "10.0.20.1",
      "mgt_netmask": "255.255.255.0",
      "migration_data_size": null,
      "migration_speed": null,
      "name": "CN-BJ-SMTX-Prod-Cls01",
      "ntp_mode": "EXTERNAL",
      "ntp_servers": [
          "10.0.0.2",
          "ntp.c89.fun",
          "10.0.0.1"
      ],
      "nvme_over_rdma_enabled": false,
      "nvme_over_tcp_enabled": false,
      "nvmf_enabled": false,
      "pmem_enabled": false,
      "provisioned_cpu_cores": 8,
      "provisioned_cpu_cores_for_active_vm": 8,
      "provisioned_for_active_vm_ratio": 0.222222222222222,
      "provisioned_memory_bytes": 20401094656,
      "provisioned_ratio": 0.222222222222222,
      "rdma_enabled": false,
      "recommended_cpu_models": [
          "EPYC"
      ],
      "recover_data_size": 0,
      "recover_speed": 0,
      "reserved_cpu_cores_for_system_service": 36,
      "running_vm_num": 1,
      "settings": {
          "id": "cmg6y1cpy05bw0958e6jofe6z"
      },
      "software_edition": "ENTERPRISE",
      "stopped_vm_num": 0,
      "stretch": false,
      "suspended_vm_num": 0,
      "total_cache_capacity": 10426449395712,
      "total_cpu_cores": 72,
      "total_cpu_hz": 178488000000,
      "total_cpu_models": [
          "host_passthrough",
          "Dhyana",
          "EPYC",
          "EPYC-IBPB",
          "Opteron_G3",
          "Opteron_G2",
          "Opteron_G1"
      ],
      "total_cpu_sockets": 3,
      "total_data_capacity": 14491697545216,
      "total_memory_bytes": 403962826752,
      "type": "SMTX_OS",
      "upgrade_tool_version": "6.2.0-rc61",
      "used_cpu_hz": 27011184000,
      "used_data_space": 0,
      "used_memory_bytes": 37145039556.9504,
      "valid_data_space": 14491697545216,
      "vcenterAccount": null,
      "vdses": [
          {
              "id": "cmg6y171e069p0958lhmew8to",
              "name": "vDS-Storage-Network"
          },
          {
              "id": "cmg6y171e069q0958ncrda8ue",
              "name": "vds-ovsbr-internal"
          },
          {
              "id": "cmg6y171e069r09587gmque13",
              "name": "vDS-MgMt-Network"
          },
          {
              "id": "cmg6y171e069s09589gq666ck",
              "name": "vDS-Prod-Network"
          }
      ],
      "version": "6.2.0",
      "vhost_enabled": true,
      "vm_folders": [],
      "vm_num": 1,
      "vm_templates": [],
      "vms": [
          {
              "id": "cmg6y18ig0050ro5gk3urcrd4",
              "name": "cloudtower"
          }
      ],
      "witness": null,
      "zones": []
  }


# 06-通过cloudtower配置集群

  ## 配置默认存储策略为双副本且开启精简配置
  请求网址
  https://10.0.20.220/api
  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（id是集群设置ID，通过查询集群详情获取；default_storage_policy是存储策略名称，REPLICA_2_THIN_PROVISION表示双副本且开启精简配置；default_storage_policy_replica_num是副本数量，2表示双副本；default_storage_policy_ec_k和default_storage_policy_ec_m是纠删码参数，开启纠删码时需要设置，未开启纠删码时保持为null；default_storage_policy_thin_provision表示是否开启精简配置，true表示开启）

  {"operationName":"updateClusterSettings","variables":{"data":{"default_storage_policy":"REPLICA_2_THIN_PROVISION","default_storage_policy_replica_num":2,"default_storage_policy_ec_k":null,"default_storage_policy_ec_m":null,"default_storage_policy_thin_provision":true},"where":{"id":"cmg6y1cpy05bw0958e6jofe6z"}},"query":"mutation updateClusterSettings($data: ClusterSettingsUpdateInput!, $where: ClusterSettingsWhereUniqueInput!) {\n  updateClusterSettings(where: $where, data: $data) {\n    id\n    default_ha\n    default_ha_priority\n    enabled_iscsi\n    default_storage_policy\n    default_storage_policy_replica_num\n    default_storage_policy_ec_k\n    default_storage_policy_ec_m\n    default_storage_policy_thin_provision\n    default_storage_encryption\n    __typename\n  }\n}\n"}

  响应示例（确认返回的default_storage_policy、default_storage_policy_replica_num和default_storage_policy_thin_provision字段值正确）
  {
      "data": {
          "updateClusterSettings": {
              "id": "cmg6y1cpy05bw0958e6jofe6z",
              "default_ha": null,
              "default_ha_priority": "LEVEL_2_MEDIUM",
              "enabled_iscsi": null,
              "default_storage_policy": "REPLICA_2_THIN_PROVISION",
              "default_storage_policy_replica_num": 2,
              "default_storage_policy_ec_k": null,
              "default_storage_policy_ec_m": null,
              "default_storage_policy_thin_provision": true,
              "default_storage_encryption": null,
              "__typename": "ClusterSettings"
          }
      }
  }



  ## 配置监控面板
  参考init脚本中配置监控面板部分，使用cloudtower提供的接口配置监控面板

  ## 获取所有报警规则
  请求网址
  https://cloudtower-ip/api

  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷
  {"operationName":"globalAlertRules","variables":{"skip":0,"first":50,"where":{"AND":[{"AND":[{"alert_rules_some":{}},{"name_not_starts_with":"elf_"},{"name_not_starts_with":"scvm_"},{"name_not_starts_with":"vsphere_"},{"name_not_starts_with":"witness_"},{"name_not_starts_with":"zone"},{"name_not_starts_with":"metro_"},{"name_not_starts_with":"system."},{"object_not_in":["SKS_SERVICE","SKS_REGISTRY","SKS_CLUSTER","SKS_CLUSTER_NODE","SKS_PV","SKS_PVC"]}]}]},"orderBy":"id_ASC"},"query":"query globalAlertRules($where: GlobalAlertRuleWhereInput, $orderBy: GlobalAlertRuleOrderByInput, $skip: Int, $first: Int) {\n  globalAlertRules(where: $where, orderBy: $orderBy, skip: $skip, first: $first) {\n    message\n    thresholds {\n      severity\n      __typename\n    }\n    object\n    id\n    disabled\n    name\n    alert_rules {\n      id\n      customized\n      disabled\n      thresholds {\n        severity\n        value\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  globalAlertRulesConnection(where: $where) {\n    aggregate {\n      count\n      __typename\n    }\n    __typename\n  }\n}\n"}

  返回示例（id字段是全局告警规则ID，后续配置集群存储容量告警时会使用；alert_rules字段中包含了各个集群的告警规则ID，后续配置集群存储容量告警时会使用）

  {
    "data": {
        "globalAlertRules": [
            {
                "message": "集群存储空间使用率超过 { .threshold }。 ",
                "thresholds": [
                    {
                        "severity": "CRITICAL",
                        "__typename": "Thresholds"
                    },
                    {
                        "severity": "NOTICE",
                        "__typename": "Thresholds"
                    }
                ],
                "object": "CLUSTER",
                "id": "cmixj2d6i010h0958iyqgxpkw",
                "disabled": false,
                "name": "zbs_cluster_data_space_use_rate",
                "alert_rules": [
                    {
                        "id": "cmixjesv402dy0958nfm2u2d5",
                        "customized": false,
                        "disabled": false,
                        "thresholds": [
                            {
                                "severity": "CRITICAL",
                                "value": 90,
                                "__typename": "Thresholds"
                            },
                            {
                                "severity": "NOTICE",
                                "value": 80,
                                "__typename": "Thresholds"
                            }
                        ],
                        "__typename": "AlertRule"
                    }
                ],
                "__typename": "GlobalAlertRule"
            }
            示例仅供参考，省略其他报警规则
        ],
        "globalAlertRulesConnection": {
            "aggregate": {
                "count": 94,
                "__typename": "AggregateGlobalAlertRule"
            },
            "__typename": "GlobalAlertRuleConnection"
        }
    }
  }

  ## 配置集群存储容量告警
  请求网址
  https://cloudtower-ip/api
  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（threshold是当前存储容量告警阈值，默认值为80，表示使用率达到80%时触发告警，这个需要修改为“（主机数-1/主机数）-5%”，例如该集群三台主机那么应该是61%，其他主机数量以此类推；cluster_id是集群ID，通过关联集群时返回的ID）
{"operationName":"updateGlobalAlertRule","variables":{"where":{"id":"cmixj2d6i010h0958iyqgxpkw"},"data":{"thresholds":[{"value":80,"severity":"NOTICE","quantile":0,"__typename":"Thresholds"},{"value":90,"severity":"CRITICAL","quantile":0,"__typename":"Thresholds"}],"alert_rules":{"update":[{"where":{"id":"cmixjesv402dy0958nfm2u2d5"},"data":{"customized":true,"disabled":false,"thresholds":[{"value":90,"severity":"CRITICAL","quantile":0,"__typename":"Thresholds"},{"value":60,"severity":"NOTICE","quantile":0,"__typename":"Thresholds"}]}}]},"disabled":false}},"query":"mutation updateGlobalAlertRule($data: GlobalAlertRuleUpdateInput!, $where: GlobalAlertRuleWhereUniqueInput!) {\n  updateGlobalAlertRule(data: $data, where: $where) {\n    id\n    disabled\n    thresholds {\n      value\n      severity\n      __typename\n    }\n    alert_rules {\n      id\n      disabled\n      customized\n      thresholds {\n        value\n        severity\n        __typename\n      }\n      cluster {\n        id\n        name\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"}

  返回示例（threshold字段是当前存储容量告警阈值，默认值为80，表示使用率达到80%时触发告警）
{
    "data": {
        "updateGlobalAlertRule": {
            "id": "cmixj2d6i010h0958iyqgxpkw",
            "disabled": false,
            "thresholds": [
                {
                    "value": 90,
                    "severity": "CRITICAL",
                    "__typename": "Thresholds"
                },
                {
                    "value": 61,
                    "severity": "NOTICE",
                    "__typename": "Thresholds"
                }
            ],
            "alert_rules": [
                {
                    "id": "cmixjesv402dy0958nfm2u2d5",
                    "disabled": false,
                    "customized": true,
                    "thresholds": [
                        {
                            "value": 90,
                            "severity": "CRITICAL",
                            "__typename": "Thresholds"
                        },
                        {
                            "value": 60,
                            "severity": "NOTICE",
                            "__typename": "Thresholds"
                        }
                    ],
                    "cluster": {
                        "id": "cmixjeoxm038p09587apv138a",
                        "name": "CN-BJ-SMTX-Prod-Cls01",
                        "__typename": "Cluster"
                    },
                    "__typename": "AlertRule"
                }
            ],
            "__typename": "GlobalAlertRule"
        }
    }
}

  ## 配置机架拓扑（待补充）
  当前计划使用单独的表格标记机架拓扑信息，后续通过脚本调用cloudtower接口配置机架拓扑




# 07-部署其他管理组件（可选）

  ## 部署OBS

  ### 上传Observability安装包
  请求网址
  https://10.0.20.2/api/ovm-operator/api/v3/chunkedUploads
  请求方法
  POST

  header
  Authorization: token（通过cloudtower登录接口获取的token）

  payload（文件名应该为Observability-X86_64-*.tar.gz，如果有多个，取最高版本）
  {"origin_file_name":"Observability-X86_64-v1.4.2-release.20250926-24.tar.gz"}

  响应
  
  {
    "id": "36ao223edNlQceIC0saWhAXj3lE",
    "package_name": "",
    "offset": "0",
    "status": "UPLOADING",
    "origin_file_name": "Observability-X86_64-v1.4.2-release.20250926-24.tar.gz",
    "error_code": "",
    "error_message": "",
    "package_id": "",
    "create_time": "2025-12-09T04:17:12.435063652Z",
    "update_time": "2025-12-09T04:17:12.435063652Z"
}

  ### 进行部署

  ## 部署备份
  
  ### 上传备份安装包

  请求网址
  https://your_tower_url/api
  请求方法
  POST

  header
  Authorization: token（通过cloudtower登录接口获取的token）
  Content-Type: multipart/form-data
  Content-Language: en-US


  载荷
  {"operationName":"createUploadTask","variables":{"data":{"status":"INITIALIZING","current_chunk":1,"chunk_size":4194304,"resource_type":"CLOUDTOWER_APPLICATION_PACKAGE","size":426394976,"args":{"name":"smtx-backup-dr-x86_64-2.2.1.tar.gz","package_name":"iomesh-backup"},"started_at":"2025-12-09T04:49:01.038Z"}},"query":"mutation createUploadTask($data: UploadTaskCreateInput!) {\n  createUploadTask(data: $data) {\n    id\n    current_chunk\n    chunk_size\n    __typename\n  }\n}\n"}

  ### 进行部署

# 08-集群巡检

 ## 调用cloudtower巡检中心接口
  请求网址
  https://10.0.20.220/api/inspector/api/v3/jobs
  请求方法
  POST

  header
  Authorization：eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（version是固定值不变；cluster_uuids是集群ID，来源关联集群时返回的ID；user_defined_items_names是需要执行的巡检项，固定值不变）
  {"version":"1.1.1-rc.11","cluster_uuids":["30724c9c-9657-46af-9c55-3857c8f165c1"],"user_defined_items_names":["master_redundancy_check","cluster_mem_usage_check","cluster_cpu_usage_check","host_disk_remaining_life_percent","host_power_is_on","host_disk_is_healthy","host_unhealthy_disk_is_offline","event_disk_remove","event_slot_disk_remove","event_disk_add","sensor_check","power_health_check","bmc_selftest","fan_check","ipmi_account_is_valid","chassis_selftest","hotfix_package_check","worker_status_check","worker_num_check","job_duration_check","failed_job_check","host_service_health","host_service_resident_memory_bytes","host_service_is_running","log_dir_usage_check","host_cpu_overall_usage_percent","host_memory_usage_percent","host_time_diff_with_ntp_leader_seconds","cluster_can_sync_time_with_external_ntp_server","cluster_can_connect_to_external_ntp_server","mongo_data_size_check","root_disk_usage_check","meta_partition_usage_check","sys_partition_raid_is_normal","sys_boot_health_check","zk_cfg_check","zk_role_check","zk_primary_check","primary_check","status_check","zk_status_check","system_config_check","third_party_software_check","host_storage_network_can_ping","host_management_network_can_ping","host_access_network_can_ping","host_to_host_max_ping_time_ns","host_work_status_is_unknown","host_bond_slave_is_normal","default_gateway_check","associated_nic_num_check","network_loss_package_check","zbs_cluster_data_space_use_rate","zbs_chunk_data_space_use_rate","cluster_storage_usage_check","zbs_cluster_chunks_unsafe_failure_space","partition_status_check","lsm_info_check","zbs_cluster_pending_migrate_bytes","zbs_chunk_avg_readwrite_latency_ns","zbs_chunk_connect_status","zbs_chunk_maintenance_mode","zbs_cluster_chunks_without_topo","zbs_chunk_dirty_cache_ratio","zbs_zone_maximum_proportion_of_rack_space","zbs_rack_maximum_proportion_of_brick_space","disk_max_sectors_kb_check","lsm2db_manifest_size_check","journal_status_check","dead_data_check","cache_status_check","recover_data_check","meta_leader_check","zbs_zk_hosts_cfg_check","elf_cluster_cpu_model_not_recommended","elf_vm_placement_expire","elf_vm_placement_status","elf_cluster_cpu_model_incompatible","elf_host_ha_status","vm_zero_page_refcount_check","vm_uuid_duplicate_check","without_vm_uuid_check"]}

  请求返回（id字段是巡检任务ID，后续查询巡检结果时会使用；VERSION版本是固定值）
  {
    "id": "33QtcKTFcCTCTdHOqbO4i65qOMT",
    "version": "1.1.1-rc.11",
    "cluster_uuids": [
        "30724c9c-9657-46af-9c55-3857c8f165c1"
    ],
    "cluster_names": {},
    "user_defined_items_names": [
        "master_redundancy_check",
        "cluster_mem_usage_check",
        …………省略…………
    ]
  }

 ## 导出巡检结果保存到本地
  先创建导出请求
  请求网址
  https://10.0.20.220/api/inspector/api/v3/jobs/33QtcKTFcCTCTdHOqbO4i65qOMT:exportReport?format=word
  请求方法
  POST

  header
  Authorization: eyJhbGciOiJIUzI1NiJ9.Y21nNnduZ3FiMDM3ZzA5NTg2a2Jwb2owMw.Z4w1Q06Kp6jWxDYhFQBy3MEfRN8Aj9SHxSuBY_FPE04

  载荷（cluster_uuid是集群ID，来源关联集群时返回的ID；items_names是需要导出的巡检项，固定值不变；graph_duration_months是图表时间范围，固定为6个月）这里的载荷需要使用format=word作为查询字符串参数
  {"options":[{"cluster_uuid":"30724c9c-9657-46af-9c55-3857c8f165c1","items_names":["host_power_is_on","host_bond_slave_is_normal","elf_cluster_cpu_model_not_recommended","zbs_cluster_pending_migrate_bytes","master_redundancy_check","cluster_cpu_usage_check","cluster_mem_usage_check","host_disk_remaining_life_percent","event_disk_remove","event_slot_disk_remove","event_disk_add","ipmi_account_is_valid","power_health_check","fan_check","sensor_check","bmc_selftest","chassis_selftest","elf_cluster_cpu_model_incompatible","elf_vm_placement_expire","elf_vm_placement_status","vm_zero_page_refcount_check","vm_uuid_duplicate_check","without_vm_uuid_check","host_management_network_can_ping","host_storage_network_can_ping","host_access_network_can_ping","host_to_host_max_ping_time_ns","host_work_status_is_unknown","network_loss_package_check","default_gateway_check","associated_nic_num_check","hotfix_package_check","worker_status_check","worker_num_check","failed_job_check","job_duration_check","primary_check","status_check","host_service_is_running","host_service_health","host_cpu_overall_usage_percent","root_disk_usage_check","meta_partition_usage_check","log_dir_usage_check","mongo_data_size_check","sys_partition_raid_is_normal","sys_boot_health_check","system_config_check","third_party_software_check","zk_status_check","zk_role_check","zk_primary_check","zk_cfg_check","zbs_cluster_data_space_use_rate","zbs_chunk_avg_readwrite_latency_ns","zbs_chunk_connect_status","zbs_chunk_data_space_use_rate","zbs_chunk_maintenance_mode","zbs_cluster_chunks_without_topo","zbs_cluster_chunks_unsafe_failure_space","zbs_chunk_dirty_cache_ratio","zbs_zone_maximum_proportion_of_rack_space","zbs_rack_maximum_proportion_of_brick_space","meta_leader_check","cache_status_check","journal_status_check","partition_status_check","recover_data_check","dead_data_check","zbs_zk_hosts_cfg_check","cluster_storage_usage_check","lsm2db_manifest_size_check","disk_max_sectors_kb_check","lsm_info_check"],"graph_duration_months":6}]}

  返回示例（filename字段是导出文件名称，后续下载时会使用）
  {
      "filename": "InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip"
  }

  第二步，查询导出状态，每隔1秒查询一次，直到status字段为EXPORT_SUCCEEDED表示导出成功，可以进行下载
  请求网址
  https://10.0.20.220/api/inspector/api/v3/export/status?filename=InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip
  请求方法
  GET

  载荷（这里的filename需要使用上一步返回的filename值作为
  查询字符串参数
  filename=InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip

  返回（status字段EXPORT_RUNNING表示正在导出，等到status字段为EXPORT_SUCCEEDED表示导出成功，可以进行下载）
  {
      "filename": "InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip",
      "status": "EXPORT_SUCCEEDED"
  }

  第三步，下载导出文件，保存到程序目录下的artifacts目录
  请求网址
  https://10.0.20.220/api/inspector/api/v1/export/download?filename=InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip
  请求方法
  GET

  载荷
  查询字符串参数
  filename=InspectorReport-2025-10-01-03-45-27-33QtcKTFcCTCTdHOqbO4i65qOMT.zip


# 09-创建测试负载

  ## 导入ovf虚拟机 PAT
    ### 导入ovf

    ### 配置网卡

    ### 启动

    ### 配置IP

    ### 创建PAT用户

    ### 创建测试对象

    ### 创建任务组

  ## 导入OVF虚拟机 FIO

    ### 导入ovf

    ### 配置网卡

    ### 启动

    ### 配置IP

# 10-性能与可靠性测试

  ## 通过PAT 接口创建测试任务
    待补充
    ### 创建测试任务

    ### 启动测试任务

    ### 查询测试任务状态

    ### 导出测试结果


# 11-收尾清理
待补充

# 其他API接口
  ## 查询fisheye存储策略uuid

  https://10.0.20.211/api/v2/storage_policies
  GET方法

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f
  host：10.0.20.210（是api请求url的主机地址）

  返回示例（只有一个默认存储策略default storage policy，如果有其他存储策略这里会返回多个，但是使用默认存储策略，这个存储策略uuid写入变量storage_policy_uuid）
{
    "data": [
        {
            "created_time": 1759223510,
            "datastores": [
                "zbs-iscsi-datastore-8c99be1a-f7d9-4b0e-a115-748647081b7c"
            ],
            "description": "default storage policy",
            "modified_time": 1759243723,
            "name": "default",
            "read_only": false,
            "replica_num": 2,
            "resource_state": "in-use",
            "storage_pool_id": "system",
            "stripe_num": 4,
            "stripe_size": 262144,
            "thin_provision": true,
            "type": "replica",
            "uuid": "dce52578-3824-4b34-97a2-af09950bb0ac",
            "whitelist": "10.0.21.211,10.0.21.213,10.0.21.212"
        }
    ],
    "ec": "EOK",
    "error": {}
}


  ## 查询管理网络VDS及业务网络VDS






  ## 查询iso 的iscsi路径

  在创建cloudtower iso上传卷时，返回内容中的 image_path 字段即为该iso的iscsi路径








