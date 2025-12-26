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

  ## 上传虚拟机工具（SVT）
  通过接口首先创建SVT卷
  请求网址（IP应该是优先使用集群VIP，其次是主机IP，name是上传的文件名称，size是上传的文件大小，单位是字节）
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


  ## 配置CPU兼容性

  ### 第一步，获取当前集群的推荐CPU兼容性
  请求网址
  https://10.0.20.10/api/v2/elf/cluster_recommended_cpu_models
  请求方法
  GET
  
  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  响应示例（其中cpu_models字段值即为当前集群推荐的CPU兼容性，第二步即使用这个字段构建载荷）
  {
  "data": {
    "cpu_models": [
      "EPYC"
    ]
  },
  "ec": "EOK",
  "error": {}
  }

  ### 第二步，配置CPU兼容性
  请求网址
  https://10.0.20.10/api/v2/elf/cluster_cpu_compatibility
  请求方法
  PUT

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  载荷
  {"cpu_model":"EPYC"}

  响应示例
  {
  "data": {},
  "ec": "EOK",
  "error": {}
  }


  ### 第三步，验证CPU兼容性配置是否成功
  请求网址
  https://10.0.20.10/api/v2/elf/cluster_cpu_compatibility
  请求方法
  GET

  添加header （这部分的x-smartx-token是登录fisheye获取token获取的）
  x-smartx-token：df91526d34a94dc9bada16437e1c579f

  响应示例（其中cpu_model字段值即为当前集群配置的CPU兼容性，应该与上一步配置的值一致）
  {
  "data": {
    "cpu_model": "EPYC"
  },
  "ec": "EOK",
  "error": {}
  }



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

  响应（license_serial字段是cloudtower序列号，写入规划表 集群管理信息 sheet 的 M3 格）
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
  
  第零步，准备cookie
  通过模拟浏览器的Cloudtower登录接口获取cookie，后续上传安装包时需要使用
  请求网址
  https://10.0.20.2/api
  请求方法
  POST
  载荷（密码是经过base64编码后的密码，密码来源于规划表中Cloudtower的管理员密码，默认为HC!r0cks）
  {"operationName":"login","variables":{"data":{"username":"root","password":"NmQwNTQ2MTI4MDQxMjgzYTk3NDU3OGZmYjk3NmFhNGM6dm40by9nOE0xZ0ZjVmxBSmR2Nmk3QT09","source":"LOCAL","auth_config_id":null}},"query":"mutation login($data: LoginInput!) {\n  login(data: $data, effect: {encoded: true}) {\n    token\n    uid\n    need_mfa\n    mfa_meta {\n      recipient\n      mid\n      type\n      valid\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应标头（包含后续所需要的cookie信息）
  set-cookie
  connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k; Path=/; HttpOnly; Secure; SameSite=Strict; HttpOnly
  set-cookie
  path=/; HttpOnly; Secure; SameSite=Strict

  响应体（包含JWT token）
  {
    "data": {
        "login": {
            "token": "eyJhbGciOiJIUzI1NiJ9.Y21qY293MXcyMDM2aDA5NTg3eDJ5NndtZw.Cx4q7xxVWBtXsyFVhPN0PQ7fgRBdJMjq1Sd2_eEnHbM",
            "uid": null,
            "need_mfa": null,
            "mfa_meta": null,
            "__typename": "Login"
        }
    }
}


  第一步先请求上传接口，获取上传ID

  请求网址
  https://10.0.20.2/api/ovm-operator/api/v3/chunkedUploads
  请求方法
  POST

  header（这个接口需要使用Basic认证，用户名和密码为o11y:HC!r0cks，base64编码后是bzExeTpIQyFyMGNrcw==）
  Authorization: Basic bzExeTpIQyFyMGNrcw==
  cookie: path=/; path=/; path=/; connect.sid=s%3Acmjkvx3x8000v7zud0gia7h1k.r4B9XtW6EFvHLPV4YN5xT%2FS07Mflgj4Gh9ipqqVM%2FwA

  payload（文件名应该为Observability-X86_64-*.tar.gz，如果有多个，取最高版本）
  {"origin_file_name":"Observability-X86_64-v1.4.2-release.20250926-24.tar.gz"}

  响应
  {
    "id": "37JudNjModKfSG1mWKbEhx9d4Qa",
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


  第二步，使用返回的ID分片上传安装包
  请求网址
  https://10.0.20.2/api/ovm-operator/api/v1/chunkedUploads
  请求方法
  POST

  header（这个接口需要使用Basic认证，用户名和密码为o11y:HC!r0cks，base64编码后是bzExeTpIQyFyMGNrcw==）
  Authorization: Basic bzExeTpIQyFyMGNrcw==
  content-length: 4194612
  content-type: ultipart/form-data; boundary=----WebKitFormBoundaryesV20WkYlx2K8Kl3
  content-encoding
  gzip
  content-type
  text/plain; charset=utf-8
  cookie: path=/; path=/; path=/; connect.sid=s%3Acmjkvx3x8000v7zud0gia7h1k.r4B9XtW6EFvHLPV4YN5xT%2FS07Mflgj4Gh9ipqqVM%2FwA

  载荷
  file
  （二进制）
  id
  37JudNjModKfSG1mWKbEhx9d4Qa

  返回
  {"id":"37JudNjModKfSG1mWKbEhx9d4Qa","offset":4194304,"status":1,"origin_file_name":"Observability-X86_64-v1.4.2-release.20250926-24.tar.gz","create_time":{"seconds":1766633581,"nanos":668054414},"update_time":{"seconds":1766633582,"nanos":390462362}}


  第三步，所有分片上传完成后，调用完成接口
  请求网址(37JudNjModKfSG1mWKbEhx9d4Qa是上传ID,第二步上传时使用的ID,来源是第一步返回结果；commit接口用于通知服务器上传完成)
  https://10.0.20.2/api/ovm-operator/api/v3/chunkedUploads/37JudNjModKfSG1mWKbEhx9d4Qa:commit
  请求方法
  POST

  header（这个接口需要使用Basic认证，用户名和密码为o11y:HC!r0cks，base64编码后是bzExeTpIQyFyMGNrcw==）
  Authorization: Basic bzExeTpIQyFyMGNrcw==
  x-user-id:cmjcow1w2036h09587x2y6wmg
  cookie: path=/; path=/; path=/; connect.sid=s%3Acmjkvx3x8000v7zud0gia7h1k.r4B9XtW6EFvHLPV4YN5xT%2FS07Mflgj4Gh9ipqqVM%2FwA


  第四步，验证安装包已上传成功
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  Authorization: token（通过cloudtower登录接口获取的token）
  cookie: path=/; path=/; path=/; connect.sid=s%3Acmjkvx3x8000v7zud0gia7h1k.r4B9XtW6EFvHLPV4YN5xT%2FS07Mflgj4Gh9ipqqVM%2FwA

  载荷
  {"operationName":"observabilityInstanceAndApps","variables":{},"query":"query observabilityInstanceAndApps {\n  bundleApplicationPackages {\n    id\n    name\n    version\n    arch\n    application_packages {\n      id\n      architecture\n      version\n      applications {\n        id\n        name\n        __typename\n      }\n      __typename\n    }\n    host_plugin_packages {\n      id\n      arch\n      version\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationInstances {\n    id\n    name\n    status\n    application {\n      id\n      instances {\n        id\n        vm {\n          id\n          status\n          cpu_usage\n          memory_usage\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    vm_spec {\n      ip\n      subnet_mask\n      gateway\n      vlan_id\n      vcpu_count\n      memory_size_bytes\n      storage_size_bytes\n      __typename\n    }\n    description\n    connected_clusters {\n      id\n      name\n      status\n      migration_status\n      cluster {\n        id\n        name\n        hosts {\n          id\n          name\n          __typename\n        }\n        type\n        __typename\n      }\n      host_plugin {\n        id\n        host_plugin_instances\n        __typename\n      }\n      observability_connected_cluster {\n        id\n        traffic_enabled\n        status\n        __typename\n      }\n      __typename\n    }\n    bundle_application_package {\n      id\n      version\n      arch\n      __typename\n    }\n    health_status\n    connected_system_services {\n      id\n      type\n      tenant_id\n      system_service {\n        id\n        name\n        __typename\n      }\n      instances {\n        state\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationConnectedClusters {\n    id\n    name\n    status\n    migration_status\n    cluster {\n      id\n      name\n      local_id\n      connect_state\n      version\n      type\n      __typename\n    }\n    bundle_application_instance {\n      id\n      name\n      status\n      health_status\n      bundle_application_package {\n        id\n        version\n        __typename\n      }\n      vm_spec {\n        ip\n        __typename\n      }\n      connected_clusters {\n        id\n        name\n        cluster {\n          id\n          local_id\n          name\n          __typename\n        }\n        host_plugin {\n          id\n          host_plugin_instances\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    observability_connected_cluster {\n      id\n      traffic_enabled\n      status\n      __typename\n    }\n    __typename\n  }\n}\n"}

  返回（需要确认bundleApplicationPackages中包含Observability安装包，且版本正确，v1.4.2-release.20250926应与上传包文件名中的对应版本字段匹配）
  {
    "data": {
        "bundleApplicationPackages": [
            {
                "id": "cmjkxevr404o20958p420551n",
                "name": "Observability",
                "version": "v1.4.2-release.20250926",
                "arch": "X86_64",
                "application_packages": [
                    {
                        "id": "cmjkxe26b04dh0958qv9ieypw",
                        "architecture": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "applications": [],
                        "__typename": "CloudTowerApplicationPackage"
                    }
                ],
                "host_plugin_packages": [
                    {
                        "id": "cmjkxeerk04il0958bxwa10oi",
                        "arch": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    },
                    {
                        "id": "cmjkxergl04nl0958slh829io",
                        "arch": "AARCH64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    }
                ],
                "__typename": "BundleApplicationPackage"
            }
        ],
        "bundleApplicationInstances": [],
        "bundleApplicationConnectedClusters": []
    }
}


  ### 等待Observability安装包处理完成
  https://10.0.20.2/v2/api/get-tasks
  post

  header
  Authorization: token（通过cloudtower登录接口获取的token）

  载荷
  无

  响应类似如下（需要确认有下列两个任务，且状态均为SUCCESSED）
  {
        "args": {},
        "cluster": null,
        "description": "Create Installation package Observability-X86_64-v1.4.2-release.20250926-24.tar.gz",
        "error_code": null,
        "error_message": null,
        "finished_at": "2025-12-25T06:31:40.000Z",
        "id": "cmjl27r7x0huh0958br25ouk3",
        "internal": false,
        "key": null,
        "local_created_at": "2025-12-25T06:26:25.000Z",
        "progress": 0,
        "resource_id": null,
        "resource_mutation": "",
        "resource_rollback_error": null,
        "resource_rollback_retry_count": null,
        "resource_rollbacked": null,
        "resource_type": null,
        "snapshot": "",
        "started_at": "2025-12-25T06:26:25.000Z",
        "status": "SUCCESSED",
        "steps": [],
        "type": null,
        "user": null
    },
    {
        "args": {
            "Hash": "5c67dcd21a874675b933095ce26153ed2882132f69dfd22966a01c31ec4e235e"
        },
        "cluster": null,
        "description": "Create Application package observability-X86_64-v1.4.2-release.20250926.tar.gz",
        "error_code": null,
        "error_message": null,
        "finished_at": "2025-12-25T06:31:02.000Z",
        "id": "cmjl2bjf40i1709584fx0fg8q",
        "internal": false,
        "key": null,
        "local_created_at": "2025-12-25T06:29:21.000Z",
        "progress": 1,
        "resource_id": "cmjl2dpbr0ia80958fpt5hqgz",
        "resource_mutation": null,
        "resource_rollback_error": null,
        "resource_rollback_retry_count": null,
        "resource_rollbacked": null,
        "resource_type": "CloudTowerApplicationPackage",
        "snapshot": "{\"typename\":\"CloudTowerApplicationPackage\"}",
        "started_at": "2025-12-25T06:29:21.000Z",
        "status": "SUCCESSED",
        "steps": [
            {
                "current": 0,
                "finished": true,
                "key": "READ_PACKAGE",
                "per_second": 0,
                "total": null,
                "unit": null
            },
            {
                "current": 0,
                "finished": true,
                "key": "STORE_IMAGE",
                "per_second": 0,
                "total": null,
                "unit": null
            },
            {
                "current": 0,
                "finished": true,
                "key": "CREATE_PACKAGE_RESOURCE",
                "per_second": 0,
                "total": null,
                "unit": null
            }
        ],
        "type": null,
        "user": {
            "id": "cmjcojkm201zx09580vmjmbru",
            "name": "system service"
        }
    }



 

  ### 进行部署

  部署前调用解析模块，对规划表进行解析，获取OBS的IP地址等信息



  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  cookie
  path=/; path=/; connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k



  载荷
  （"name":"obs"表示部署实例名称为obs，
  "bundle_application_package":{"id":"cmjkzx3hy0ack0958emrwoy18"}中的id为Observability安装包ID，通过查询安装包时获取；
  cluster.id为要部署到的集群ID，通过查询集群时获取；
  vm_spec中的ip来源自规划表的解析结果，坐标和上下文变量为 OBS_IP = register_variable("OBS_IP", "集群管理信息", "E4", "OBS IP")
  subnet_mask、gateway来源于规划表解析的管理网络信息，可以参考init脚本中获取管理网络子网掩码和网关的方式，或者部署Cloudtower模块中的类似实现；
  vlan_id来源于规划表中default虚拟网络所在网络对应的VLAN ID（通过查询网络获取），可以参考部署Cloudtower模块中获取default虚拟网络VLAN ID的实现；
  vcpu_count、memory_size_bytes和storage_size_bytes是固定值，保持"vcpu_count":16,"memory_size_bytes":"34359738368","storage_size_bytes":"549755813888"不变
  env_vars中的PRODUCT_VENDOR字段固定为SMARTX）


  {"operationName":"createBundleApplicationInstance","variables":{"data":{"name":"obs","description":"","bundle_application_package":{"id":"cmjkzx3hy0ack0958emrwoy18"},"cluster":{"id":"cmjcow5a1038u09588mxmnop7"},"host_id":"","vm_spec":{"ip":"10.0.20.3","subnet_mask":"255.255.255.0","gateway":"10.0.20.1","vlan_id":"cmjcow96r000lqrqalh84y2nd","vcpu_count":16,"memory_size_bytes":"34359738368","storage_size_bytes":"549755813888","env_vars":{"PRODUCT_VENDOR":"SMARTX"}}}},"query":"mutation createBundleApplicationInstance($data: BundleApplicationInstanceCreateInput!) {\n  createBundleApplicationInstance(data: $data) {\n    id\n    __typename\n  }\n}\n"}

  响应
  {
    "data": {
        "createBundleApplicationInstance": {
            "id": "cmjl01uap0ap40958kidyhmr9",
            "__typename": "BundleApplicationInstance"
        }
    }
}


  ### 验证部署结果
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  cookie
  path=/; path=/; connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k


  载荷
  {"operationName":"observabilityInstanceAndApps","variables":{},"query":"query observabilityInstanceAndApps {\n  bundleApplicationPackages {\n    id\n    name\n    version\n    arch\n    application_packages {\n      id\n      architecture\n      version\n      applications {\n        id\n        name\n        __typename\n      }\n      __typename\n    }\n    host_plugin_packages {\n      id\n      arch\n      version\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationInstances {\n    id\n    name\n    status\n    application {\n      id\n      instances {\n        id\n        vm {\n          id\n          status\n          cpu_usage\n          memory_usage\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    vm_spec {\n      ip\n      subnet_mask\n      gateway\n      vlan_id\n      vcpu_count\n      memory_size_bytes\n      storage_size_bytes\n      __typename\n    }\n    description\n    connected_clusters {\n      id\n      name\n      status\n      migration_status\n      cluster {\n        id\n        name\n        hosts {\n          id\n          name\n          __typename\n        }\n        type\n        __typename\n      }\n      host_plugin {\n        id\n        host_plugin_instances\n        __typename\n      }\n      observability_connected_cluster {\n        id\n        traffic_enabled\n        status\n        __typename\n      }\n      __typename\n    }\n    bundle_application_package {\n      id\n      version\n      arch\n      __typename\n    }\n    health_status\n    connected_system_services {\n      id\n      type\n      tenant_id\n      system_service {\n        id\n        name\n        __typename\n      }\n      instances {\n        state\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationConnectedClusters {\n    id\n    name\n    status\n    migration_status\n    cluster {\n      id\n      name\n      local_id\n      connect_state\n      version\n      type\n      __typename\n    }\n    bundle_application_instance {\n      id\n      name\n      status\n      health_status\n      bundle_application_package {\n        id\n        version\n        __typename\n      }\n      vm_spec {\n        ip\n        __typename\n      }\n      connected_clusters {\n        id\n        name\n        cluster {\n          id\n          local_id\n          name\n          __typename\n        }\n        host_plugin {\n          id\n          host_plugin_instances\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    observability_connected_cluster {\n      id\n      traffic_enabled\n      status\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应类型1，正在安装中（需要确认bundleApplicationInstances中包含刚刚部署的obs实例，"id": "cmjl01uap0ap40958kidyhmr9"是部署时返回响应中的ID，状态为INSTALLING则为部署中，需要等待）
  {
    "data": {
        "bundleApplicationPackages": [
            {
                "id": "cmjkzx3hy0ack0958emrwoy18",
                "name": "Observability",
                "version": "v1.4.2-release.20250926",
                "arch": "X86_64",
                "application_packages": [
                    {
                        "id": "cmjkzw6qf0a0k0958hfmiqvwe",
                        "architecture": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "applications": [],
                        "__typename": "CloudTowerApplicationPackage"
                    }
                ],
                "host_plugin_packages": [
                    {
                        "id": "cmjkzwk0n0a6p0958yui4tdyr",
                        "arch": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    },
                    {
                        "id": "cmjkzwz700ac40958c96in94w",
                        "arch": "AARCH64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    }
                ],
                "__typename": "BundleApplicationPackage"
            }
        ],
        "bundleApplicationInstances": [
            {
                "id": "cmjl01uap0ap40958kidyhmr9",
                "name": "obs",
                "status": "INSTALLING",
                "application": {
                    "id": "cmjl01uaf0aov09585hcpo94w",
                    "instances": [],
                    "__typename": "CloudTowerApplication"
                },
                "vm_spec": {
                    "ip": "10.0.20.3",
                    "subnet_mask": "255.255.255.0",
                    "gateway": "10.0.20.1",
                    "vlan_id": "cmjcow96r000lqrqalh84y2nd",
                    "vcpu_count": 16,
                    "memory_size_bytes": "34359738368",
                    "storage_size_bytes": "549755813888",
                    "__typename": "BundleApplicationInstanceVmSpec"
                },
                "description": "",
                "connected_clusters": [],
                "bundle_application_package": {
                    "id": "cmjkzx3hy0ack0958emrwoy18",
                    "version": "v1.4.2-release.20250926",
                    "arch": "X86_64",
                    "__typename": "BundleApplicationPackage"
                },
                "health_status": null,
                "connected_system_services": [],
                "__typename": "BundleApplicationInstance"
            }
        ],
        "bundleApplicationConnectedClusters": []
    }
}


响应类型2，部署成功（"status": "SUCCESS",且vm状态为RUNNING，说明部署成功，可以进行下一步）
{
    "data": {
        "bundleApplicationPackages": [
            {
                "id": "cmjkzx3hy0ack0958emrwoy18",
                "name": "Observability",
                "version": "v1.4.2-release.20250926",
                "arch": "X86_64",
                "application_packages": [
                    {
                        "id": "cmjkzw6qf0a0k0958hfmiqvwe",
                        "architecture": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "applications": [
                            {
                                "id": "cmjl01uaf0aov09585hcpo94w",
                                "name": "observability-obs",
                                "__typename": "CloudTowerApplication"
                            }
                        ],
                        "__typename": "CloudTowerApplicationPackage"
                    }
                ],
                "host_plugin_packages": [
                    {
                        "id": "cmjkzwk0n0a6p0958yui4tdyr",
                        "arch": "X86_64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    },
                    {
                        "id": "cmjkzwz700ac40958c96in94w",
                        "arch": "AARCH64",
                        "version": "v1.4.2-release.20250926",
                        "__typename": "HostPluginPackage"
                    }
                ],
                "__typename": "BundleApplicationPackage"
            }
        ],
        "bundleApplicationInstances": [
            {
                "id": "cmjl01uap0ap40958kidyhmr9",
                "name": "obs",
                "status": "SUCCESS",
                "application": {
                    "id": "cmjl01uaf0aov09585hcpo94w",
                    "instances": [
                        {
                            "id": "cmjl060uc0bde0958r4asmm66",
                            "vm": {
                                "id": "cmjl060u70bdd0958vq8wg5q2",
                                "status": "RUNNING",
                                "cpu_usage": 0.68,
                                "memory_usage": 5.54,
                                "__typename": "Vm"
                            },
                            "__typename": "CloudTowerApplicationInstance"
                        }
                    ],
                    "__typename": "CloudTowerApplication"
                },
                "vm_spec": {
                    "ip": "10.0.20.3",
                    "subnet_mask": "255.255.255.0",
                    "gateway": "10.0.20.1",
                    "vlan_id": "cmjcow96r000lqrqalh84y2nd",
                    "vcpu_count": 16,
                    "memory_size_bytes": "34359738368",
                    "storage_size_bytes": "549755813888",
                    "__typename": "BundleApplicationInstanceVmSpec"
                },
                "description": "",
                "connected_clusters": [],
                "bundle_application_package": {
                    "id": "cmjkzx3hy0ack0958emrwoy18",
                    "version": "v1.4.2-release.20250926",
                    "arch": "X86_64",
                    "__typename": "BundleApplicationPackage"
                },
                "health_status": "NORMAL",
                "connected_system_services": [],
                "__typename": "BundleApplicationInstance"
            }
        ],
        "bundleApplicationConnectedClusters": []
    }
}

  ### 修改OBS NTP配置

  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  cookie
  path=/; path=/; connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k

  载荷（"ntp_service_url":"10.0.0.2,ntp.c89.fun,10.0.0.1"）来源于解析表的NTP服务器地址，"where":{"id":"cmjl61tvj0pdc0958uzrclg18"}中的id是obs实例ID，通过查询部署好的obs实例获取）
  {"operationName":"updateObservabilityNtpUrl","variables":{"data":{"ntp_service_url":"10.0.0.2,ntp.c89.fun,10.0.0.1"},"where":{"id":"cmjl61tvj0pdc0958uzrclg18"}},"query":"mutation updateObservabilityNtpUrl($data: NtpCommonUpdateInput!, $where: BundleApplicationInstanceWhereUniqueInput!) {\n  updateObservabilityNtpUrl(data: $data, where: $where) {\n    ntp_service_url\n    __typename\n  }\n}\n"}

  响应
  {
      "data": {
          "updateObservabilityNtpUrl": {
              "ntp_service_url": "10.0.0.2;ntp.c89.fun;10.0.0.1",
              "__typename": "UpdateNtpCommonResult"
          }
      }
  }


  ### 关联集群

  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  cookie
  path=/; path=/; connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k

  载荷（将部署好的obs实例关联到集群上，"id":"cmjl01uap0ap40958kidyhmr9"是obs的实例ID，"id_in":["cmjcow5a1038u09588mxmnop7"]是待关联到obs的集群id，通过调用查询集群模块query_cluster实现获取id）
  {"operationName":"updateBundleApplicationInstanceConnectClusters","variables":{"where":{"id":"cmjl01uap0ap40958kidyhmr9"},"data":{"connected_clusters":{"id_in":["cmjcow5a1038u09588mxmnop7"]}}},"query":"mutation updateBundleApplicationInstanceConnectClusters($where: BundleApplicationInstanceWhereInput!, $data: BundleApplicationInstanceConnectClustersInput!) {\n  updateBundleApplicationInstanceConnectClusters(where: $where, data: $data) {\n    id\n    name\n    description\n    status\n    error_code\n    vm_spec {\n      ip\n      subnet_mask\n      gateway\n      vlan_id\n      vcpu_count\n      memory_size_bytes\n      storage_size_bytes\n      __typename\n    }\n    connected_clusters {\n      id\n      name\n      cluster {\n        id\n        name\n        __typename\n      }\n      __typename\n    }\n    cluster {\n      id\n      name\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应
  {
    "data": {
        "updateBundleApplicationInstanceConnectClusters": {
            "id": "cmjl01uap0ap40958kidyhmr9",
            "name": "obs",
            "description": "",
            "status": "SUCCESS",
            "error_code": "",
            "vm_spec": {
                "ip": "10.0.20.3",
                "subnet_mask": "255.255.255.0",
                "gateway": "10.0.20.1",
                "vlan_id": "cmjcow96r000lqrqalh84y2nd",
                "vcpu_count": 16,
                "memory_size_bytes": "34359738368",
                "storage_size_bytes": "549755813888",
                "__typename": "BundleApplicationInstanceVmSpec"
            },
            "connected_clusters": [
                {
                    "id": "cmjl19lny0emi0958sn65ah7o",
                    "name": "CN-BJ-SMTX-Prod-Cls01",
                    "cluster": {
                        "id": "cmjcow5a1038u09588mxmnop7",
                        "name": "CN-BJ-SMTX-Prod-Cls01",
                        "__typename": "Cluster"
                    },
                    "__typename": "BundleApplicationConnectedCluster"
                }
            ],
            "cluster": {
                "id": "cmjcow5a1038u09588mxmnop7",
                "name": "CN-BJ-SMTX-Prod-Cls01",
                "__typename": "Cluster"
            },
            "__typename": "BundleApplicationInstance"
        }
    }
}

  ### 关联Cloudtower系统服务
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  cookie
  path=/; path=/; connect.sid=s%3Acmjkynw9e024p7zud58mscdx7.Lo9ABrnF3eWB3z7TZFin51N2%2Bz9vdi4qq7VmzhYPI7k


  载荷（只有url:"http://10.0.20.2/admin/observability/agent中的10.0.20.2是根据规划表中Cloudtower的ip填入的，其他都是固定值）
  {"operationName":"updateObservabilityConnectedSystemServices","variables":{"ovm_name":"observability","connected_system_services":[{"system_service_id":"CLOUDTOWER","system_service_name":"CloudTower","type":"CLOUDTOWER","alerting_rules":[{"name":"cluster_connect_status","type":"METRIC","metric_validator":{"interval":"30s","for":"5m","query_tmpl":"cluster_connect_status * on (_tenant_id) group_left (service_name) obs_agent_info == 0"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED"},"default_thresholds":[{"severity":"INFO","value":"0"}],"thresholds":[{"severity":"INFO","value":"0"}],"messages":[{"locale":"en-US","str":"CloudTower failed to connect to the {{ $labels.clusterType }} cluster {{ $labels.clusterName }}."},{"locale":"zh-CN","str":"CloudTower 与 {{ $labels.clusterType }} 集群 {{ $labels.clusterName }} 连接异常。"}],"causes":[{"locale":"en-US","str":"Network connectivity error or cluster status error."},{"locale":"zh-CN","str":"网络连接异常或集群运行状态异常。"}],"impacts":[{"locale":"en-US","str":"This may prevent the cluster from functioning or being managed properly."},{"locale":"zh-CN","str":"可能导致无法正常使用或管理集群。"}],"solutions":[{"locale":"en-US","str":"Please check the network connectivity or the cluster status."},{"locale":"zh-CN","str":"请确认网络连通性或集群状态。"}]},{"name":"cluster_authentication_status","type":"METRIC","metric_validator":{"interval":"30s","for":"5m","query_tmpl":"cluster_authentication_status * on (_tenant_id) group_left (service_name) obs_agent_info == 0"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED"},"default_thresholds":[{"severity":"INFO","value":"0"}],"thresholds":[{"severity":"INFO","value":"0"}],"messages":[{"locale":"en-US","str":"Cluster unreachable due to authentication failure for the {{ $labels.clusterType }} cluster {{ $labels.clusterName }}."},{"locale":"zh-CN","str":"集群无法连接，因 {{ $labels.clusterType }} 集群 {{ $labels.clusterName }} 鉴权失败。"}],"causes":[{"locale":"en-US","str":"Cluster authentication failed."},{"locale":"zh-CN","str":"集群鉴权失败。"}],"impacts":[{"locale":"en-US","str":"CloudTower failed to connect to the cluster, which may result in the cluster being unavailable or unmanageable."},{"locale":"zh-CN","str":"CloudTower 与集群连接异常，可能无法正常使用或管理集群。"}],"solutions":[{"locale":"en-US","str":"Please confirm that the administrator username and password are correct."},{"locale":"zh-CN","str":"请确认集群管理员用户名及密码。"}]},{"name":"service_cpu_usage_overload","type":"METRIC","metric_validator":{"interval":"30s","for":"10m","query_tmpl":"sum without (mode) (avg without (cpu) (rate(node_cpu_seconds_total{mode!='idle'}[2m]))) * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info * 100 > {{ .threshold }}"},"metric_descriptor":{"unit":"PERCENT"},"default_thresholds":[{"severity":"NOTICE","value":"90"}],"thresholds":[{"severity":"NOTICE","value":"90"}],"messages":[{"locale":"en-US","str":"The CPU usage of the virtual machine {{ $labels.vm_name }} running CloudTower is too high."},{"locale":"zh-CN","str":"运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的 CPU 占用过高。"}],"causes":[{"locale":"en-US","str":"The increased system load causes the vCPUs on the virtual machine running the system service to become insufficient for the service to run properly."},{"locale":"zh-CN","str":"因系统负载增大，当前运行系统服务的虚拟机的 vCPU 数量已不足以支持系统服务平稳运行。"}],"impacts":[{"locale":"en-US","str":"The system service may not run properly."},{"locale":"zh-CN","str":"可能导致系统服务无法正常提供服务。"}],"solutions":[{"locale":"en-US","str":"Scale up the system service virtual machine, or contact technical support for assistance."},{"locale":"zh-CN","str":"提高该系统服务虚拟机的资源配置，或联系售后技术支持。"}]},{"name":"service_disk_usage_overload","type":"METRIC","metric_validator":{"interval":"30s","for":"5m","query_tmpl":"100 - (node_filesystem_avail_bytes{mountpoint='/'} / node_filesystem_size_bytes{mountpoint='/'}) * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info * 100 > {{ .threshold }}"},"metric_descriptor":{"unit":"PERCENT"},"default_thresholds":[{"severity":"NOTICE","value":"90"}],"thresholds":[{"severity":"NOTICE","value":"90"}],"messages":[{"locale":"en-US","str":"The storage capacity on the virtual machine {{ $labels.vm_name }} running CloudTower is insufficient."},{"locale":"zh-CN","str":"运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的存储空间不足。"}],"causes":[{"locale":"en-US","str":"The increased system load causes the storage capacity on the virtual machine running the system service to become insufficient for the service to run properly."},{"locale":"zh-CN","str":"因系统负载增大，当前运行系统服务的虚拟机的存储空间已不足以支持系统服务平稳运行。"}],"impacts":[{"locale":"en-US","str":"The system service may not run properly."},{"locale":"zh-CN","str":"可能导致系统服务无法正常提供服务。"}],"solutions":[{"locale":"en-US","str":"Scale up the system service virtual machine, or contact technical support for assistance."},{"locale":"zh-CN","str":"提高该系统服务虚拟机的资源配置，或联系售后技术支持。"}]},{"name":"service_memory_usage_overload","type":"METRIC","metric_validator":{"interval":"30s","for":"5m","query_tmpl":"100 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100 * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info > {{ .threshold }}"},"metric_descriptor":{"unit":"PERCENT"},"default_thresholds":[{"severity":"NOTICE","value":"80"}],"thresholds":[{"severity":"NOTICE","value":"80"}],"messages":[{"locale":"en-US","str":"The memory usage of the virtual machine {{ $labels.vm_name }} running CloudTower is too high."},{"locale":"zh-CN","str":"运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的内存使用率过高。"}],"causes":[{"locale":"en-US","str":"The increased system load causes the memory on the virtual machine running the system service to become insufficient for the service to run properly."},{"locale":"zh-CN","str":"因系统负载增大，当前运行系统服务的虚拟机的内存分配量已不足以支持系统服务平稳运行。"}],"impacts":[{"locale":"en-US","str":"The system service may not run properly."},{"locale":"zh-CN","str":"可能导致系统服务无法正常提供服务。"}],"solutions":[{"locale":"en-US","str":"Scale up the system service virtual machine, or contact technical support for assistance."},{"locale":"zh-CN","str":"提高该系统服务虚拟机的资源配置，或联系售后技术支持。"}]},{"name":"service_vm_has_no_ntp_server","type":"METRIC","metric_validator":{"interval":"30s","query_tmpl":"host_ntp_server_numbers * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info == {{ .threshold }}"},"default_thresholds":[{"severity":"INFO","value":"0"}],"thresholds":[{"severity":"INFO","value":"0"}],"messages":[{"locale":"en-US","str":"CloudTower is not configured with an NTP server."},{"locale":"zh-CN","str":"CloudTower 未配置 NTP 服务器。"}],"causes":[{"locale":"en-US","str":"CloudTower is not configured with an NTP server."},{"locale":"zh-CN","str":"CloudTower 未配置 NTP 服务器。"}],"impacts":[{"locale":"en-US","str":"The CloudTower time might be inaccurate, which affects the time display in task and monitoring functions. Other system services including backup and SKS might encounter exceptions. "},{"locale":"zh-CN","str":"CloudTower 的时间可能不准确，影响任务、监控等功能的时间显示，或造成备份与容灾、Kubernetes 等其他系统服务的功能异常。"}],"solutions":[{"locale":"en-US","str":"Configure an NTP server for CloudTower."},{"locale":"zh-CN","str":"为 CloudTower 配置 NTP 服务器。"}]},{"name":"service_vm_disconnect_with_each_ntp_server","type":"METRIC","metric_validator":{"interval":"30s","query_tmpl":"host_can_connect_with_each_ntp_server * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info == {{ .threshold }}"},"metric_descriptor":{"is_boolean":true},"default_thresholds":[{"severity":"NOTICE","value":"0"}],"thresholds":[{"severity":"NOTICE","value":"0"}],"messages":[{"locale":"en-US","str":"Failed to establish the connection between the CloudTower and the NTP server {{ $labels.ntp_server }}."},{"locale":"zh-CN","str":"CloudTower 无法与 NTP 服务器 {{ $labels.ntp_server }} 建立连接。"}],"causes":[{"locale":"en-US","str":"The current NTP server’s domain name or IP address might be invalid, or there might be a network exception."},{"locale":"zh-CN","str":"当前设置的 NTP 服务器域名、IP 地址可能无效，或存在网络异常。"}],"impacts":[{"locale":"en-US","str":"The CloudTower time might be inconsistent with the NTP server time."},{"locale":"zh-CN","str":"CloudTower 与 NTP 服务器的时间可能不同步。"}],"solutions":[{"locale":"en-US","str":"Check the network connection, or verify the validity of the external NTP server’s domain name and IP address. If the connection to the NTP server fails, you need to reconfigure a valid NTP server."},{"locale":"zh-CN","str":"检查网络连接或外部 NTP 服务器域名、IP 是否有效。若无法正常连接 NTP 服务器，则重新设置一个有效的 NTP 服务器。"}]},{"name":"service_vm_time_offset_with_ntp_leader","type":"METRIC","metric_validator":{"interval":"30s","for":"3m","query_tmpl":"host_time_offset_with_ntp_leader_seconds * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info > {{ .threshold }}"},"metric_descriptor":{"unit":"SECOND"},"default_thresholds":[{"severity":"INFO","value":"10"},{"severity":"NOTICE","value":"30"},{"severity":"CRITICAL","value":"60"}],"thresholds":[{"severity":"INFO","value":"10"},{"severity":"NOTICE","value":"30"},{"severity":"CRITICAL","value":"60"}],"messages":[{"locale":"en-US","str":"The time offset between the CloudTower and the NTP server is excessively large."},{"locale":"zh-CN","str":"CloudTower 与 NTP 服务器时间偏移量过大。"}],"causes":[{"locale":"en-US","str":"The time offset between the CloudTower and the NTP server is excessively large."},{"locale":"zh-CN","str":"CloudTower 与 NTP 服务器时间偏差过大。"}],"impacts":[{"locale":"en-US","str":"The CloudTower time is inaccurate, and the NTP service might stop synchronizing time."},{"locale":"zh-CN","str":"CloudTower 的时间不准确，且可能导致 NTP 服务停止同步。"}],"solutions":[{"locale":"en-US","str":"Contact technical support for assistance."},{"locale":"zh-CN","str":"联系售后技术支持。"}]},{"name":"cloudtower_system_service_vm_time_offset_seconds","type":"METRIC","metric_validator":{"interval":"30s","for":"3m","query_tmpl":"abs(cloudtower_system_service_vm_time_offset_seconds) * on (_tenant_id) group_left (service_name) obs_agent_info > {{ .threshold }}"},"metric_descriptor":{"unit":"SECOND"},"default_thresholds":[{"severity":"NOTICE","value":"30"},{"severity":"CRITICAL","value":"60"}],"thresholds":[{"severity":"NOTICE","value":"30"},{"severity":"CRITICAL","value":"60"}],"messages":[{"locale":"en-US","str":"The time offset between CloudTower and the system service virtual machine {{ $labels.vm_name }} is excessively large."},{"locale":"zh-CN","str":"CloudTower 与系统服务虚拟机 {{ $labels.vm_name }} 的时间偏移量过大。"}],"causes":[{"locale":"en-US","str":"The CloudTower time is inconsistent with the time of the system service virtual machine {{ $labels.vm_name }}."},{"locale":"zh-CN","str":"CloudTower 与系统服务虚拟机 {{ $labels.vm_name }} 的时间不同步。"}],"impacts":[{"locale":"en-US","str":"The system service might not be able to function properly."},{"locale":"zh-CN","str":"系统服务可能无法正常工作。"}],"solutions":[{"locale":"en-US","str":"Configure time-consistent NTP servers for the system service and CloudTower, and check the synchronization between the system service and its NTP server."},{"locale":"zh-CN","str":"为系统服务与 CloudTower 配置时间一致的 NTP 服务器，并检查系统服务与 NTP 服务器的同步情况。"}]},{"name":"cloudtower_cluster_time_offset_seconds","type":"METRIC","metric_validator":{"interval":"30s","for":"3m","query_tmpl":"abs(cloudtower_cluster_time_offset_seconds) * on (_tenant_id) group_left (service_name) obs_agent_info > {{ .threshold }}"},"metric_descriptor":{"unit":"SECOND"},"default_thresholds":[{"severity":"INFO","value":"10"},{"severity":"NOTICE","value":"30"}],"thresholds":[{"severity":"INFO","value":"10"},{"severity":"NOTICE","value":"30"}],"messages":[{"locale":"en-US","str":"The time offset between CloudTower and the cluster {{ $labels.cluster_name }} is excessively large."},{"locale":"zh-CN","str":"CloudTower 与集群 {{ $labels.cluster_name }} 的时间偏移量过大。"}],"causes":[{"locale":"en-US","str":"The CloudTower time is inconsistent with the cluster time."},{"locale":"zh-CN","str":"CloudTower 与集群的时间不同步。"}],"impacts":[{"locale":"en-US","str":"The functions on CloudTower including task and monitoring involving the cluster might have time offset."},{"locale":"zh-CN","str":"CloudTower 上与该集群相关的任务、监控等功能可能出现时间偏移。"}],"solutions":[{"locale":"en-US","str":"Configure time-consistent NTP servers for the cluster and CloudTower."},{"locale":"zh-CN","str":"为集群与 CloudTower 配置时间一致的 NTP 服务器。"}]},{"name":"everoute_service_unavailable","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"everoute_admission_everoute_phase{phase=\"Failed\"} == 1"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute service {{ $labels.everoute_displayname }} is in an abnormal state due to {{ $labels.error_code }}."},{"locale":"zh-CN","str":"Everoute 服务 {{ $labels.everoute_displayname }} 处于异常状态，原因为 {{ $labels.error_code }}。"}],"causes":[{"locale":"en-US","str":"The maintanance and management operation on the Everoute service failed."},{"locale":"zh-CN","str":"Everoute 服务运维管理操作失败。"}],"impacts":[{"locale":"en-US","str":"The Everoute service cannot work properly."},{"locale":"zh-CN","str":"Everoute 无法正常提供服务。"}],"solutions":[{"locale":"en-US","str":"Identify the reason for the failure and manually retry the previous operation, or follow Operation and Maintenance Guide to recover the Everoute service."},{"locale":"zh-CN","str":"确认操作失败原因，手动重试或按照运维管理手册恢复。"}]},{"name":"everoute_license_dfw_soon_to_expire","type":"METRIC","default_thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"0 < (everoute_admission_license_available_days{feature_type=\"DFW\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= {{ .threshold }}"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute distributed firewall license is less than {{ $value }} {{ if eq $value 1.0 }}day{{ else }}days{{ end }} from expiration."},{"locale":"zh-CN","str":"Everoute 中的分布式防火墙许可，距离过期不足 {{ $value }} 天。"}],"causes":[{"locale":"en-US","str":"The license will expire soon."},{"locale":"zh-CN","str":"许可即将过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_license_lb_soon_to_expire","type":"METRIC","default_thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"0 < (everoute_admission_license_available_days{feature_type=\"LB\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= {{ .threshold }}"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute load balancer license is less than {{ $value }} {{ if eq $value 1.0 }}day{{ else }}days{{ end }} from expiration."},{"locale":"zh-CN","str":"Everoute 中的负载均衡器许可，距离过期不足 {{ $value }} 天。"}],"causes":[{"locale":"en-US","str":"The license will expire soon."},{"locale":"zh-CN","str":"许可即将过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_license_vpc_soon_to_expire","type":"METRIC","default_thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"thresholds":[{"severity":"INFO","value":"30"},{"severity":"NOTICE","value":"14"},{"severity":"CRITICAL","value":"1"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"0 < (everoute_admission_license_available_days{feature_type=\"VPC\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= {{ .threshold }}"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute VPC networking license is less than {{ $value }} {{ if eq $value 1.0 }}day{{ else }}days{{ end }} from expiration."},{"locale":"zh-CN","str":"Everoute 中的虚拟专有云网络许可，距离过期不足 {{ $value }} 天。"}],"causes":[{"locale":"en-US","str":"The license will expire soon."},{"locale":"zh-CN","str":"许可即将过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_license_dfw_expired","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"(everoute_admission_license_available_days{feature_type=\"DFW\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= 0"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute distributed firewall license has expired."},{"locale":"zh-CN","str":"Everoute 中的分布式防火墙许可已经过期。"}],"causes":[{"locale":"en-US","str":"The license has expired."},{"locale":"zh-CN","str":"许可已经过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_license_lb_expired","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"(everoute_admission_license_available_days{feature_type=\"LB\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= 0"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute load balancer license has expired."},{"locale":"zh-CN","str":"Everoute 中的负载均衡器许可已经过期。"}],"causes":[{"locale":"en-US","str":"The license has expired."},{"locale":"zh-CN","str":"许可已经过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_license_vpc_expired","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"interval":"1m0s","for":"0s","query_tmpl":"(everoute_admission_license_available_days{feature_type=\"VPC\"} and on(feature_type) (everoute_admission_everoute_feature_enabled > 0)) <= 0"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED","is_boolean":false},"messages":[{"locale":"en-US","str":"The Everoute VPC networking license has expired."},{"locale":"zh-CN","str":"Everoute 中的虚拟专有云网络许可已经过期。"}],"causes":[{"locale":"en-US","str":"The license has expired."},{"locale":"zh-CN","str":"许可已经过期。"}],"impacts":[{"locale":"en-US","str":"Once the license expires, you cannot create new resources or edit the existing ones."},{"locale":"zh-CN","str":"许可过期后，无法创建新的资源或编辑已有资源。"}],"solutions":[{"locale":"en-US","str":"Contact after-sales support to extend the license period, or uninstall this function if you no longer need it."},{"locale":"zh-CN","str":"联系售后人员，延长许可有效期，如不再使用可卸载此功能。"}]},{"name":"everoute_binding_no_tep_ip_hosts","type":"METRIC","default_thresholds":[{"severity":"INFO","value":"0"}],"thresholds":[{"severity":"INFO","value":"0"}],"metric_validator":{"interval":"1m","for":"0s","query_tmpl":"everoute_admission_binding_no_tep_ip_hosts == 1"},"metric_descriptor":{"unit":"UNIT_UNSPECIFIED"},"messages":[{"locale":"en-US","str":"In the cluster {{ $labels.cluster_name }} associated with Everoute VPC networking, the following hosts do not have TEP IP addresses{{\":\"}} {{ $labels.hosts_name | reReplaceAll \",\" \", \" }}."},{"locale":"zh-CN","str":"Everoute 虚拟专有云网络已关联的集群 {{ $labels.cluster_name }} 中，主机 {{ $labels.hosts_name | reReplaceAll \",\" \"、\" }} 未添加 TEP IP 地址。"}],"causes":[{"locale":"en-US","str":"After scaling out the cluster, the newly added hosts are not configured with TEP IP addresses."},{"locale":"zh-CN","str":"集群扩容后，没有为新增主机配置 TEP IP 地址。"}],"impacts":[{"locale":"en-US","str":"Adding or deleting a virtual NIC of the VPC type from a virtual machine in the cluster might fail."},{"locale":"zh-CN","str":"集群中的虚拟机增加或删除 VPC 类型的虚拟网卡时可能会失败。"}],"solutions":[{"locale":"en-US","str":"Bind the ports on the hosts to the virtual distributed switch {{ $labels.vds_name }}, and add TEP IP addresses to the hosts. "},{"locale":"zh-CN","str":"将主机的网口绑定至虚拟分布式交换机 {{ $labels.vds_name }}，并为主机添加 TEP IP。"}]},{"name":"fsc_is_unhealthy","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"for":"2m","interval":"15s","query_tmpl":"(sfs_operator_fsc_unhealthy == 1 and on(sfscluster) sfs_operator_cluster_services_unavailable{service=\"etcd\"} == 0 and on(sfscluster) sfs_operator_cluster_services_unavailable{service=\"k8s-api-server\"} == 0) > {{ .threshold }}"},"metric_descriptor":{"is_boolean":true},"messages":[{"locale":"en-US","str":"The file controller {{ $labels.fsc }} of the file storage cluster {{ $labels.sfscluster }} is abnormal."},{"locale":"zh-CN","str":"文件存储集群 {{ $labels.sfscluster }} 的文件控制器 {{ $labels.fsc }} 状态异常。"}],"causes":[{"locale":"en-US","str":"The file controller is not running, the internal service component of the file controller is abnormal, or the file storage network is abnormal."},{"locale":"zh-CN","str":"文件控制器状态为未运行、文件控制器内部服务组件异常，或文件存储网络异常。"}],"impacts":[{"locale":"en-US","str":"The control service and the storage service of the file storage cluster might be affected."},{"locale":"zh-CN","str":"文件存储集群的管控服务和存储服务可能受到影响。"}],"solutions":[{"locale":"en-US","str":"Check the file controller's status and the network connectivity, or contact our technical support for assistance."},{"locale":"zh-CN","str":"检查文件控制器的运行状态、网络连接状态，或联系售后技术支持。"}]},{"name":"cluster_api_components_are_unavailable","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"for":"30s","interval":"15s","query_tmpl":"(sfs_operator_cluster_services_unavailable{service=~\"k8s-api-server|etcd\"} == 1) > {{ .threshold }}"},"metric_descriptor":{"is_boolean":true},"messages":[{"locale":"en-US","str":"The API component {{ $labels.service }} in the file storage cluster {{ $labels.sfscluster }} is abnormal."},{"locale":"zh-CN","str":"文件存储集群 {{ $labels.sfscluster }} 中的 API 组件 {{ $labels.service }} 状态异常。"}],"causes":[{"locale":"en-US","str":"The API component {{ $labels.service }} in the file storage cluster is not running, the file management network is abnormal, the file storage network is abnormal, or the file controller is not running."},{"locale":"zh-CN","str":"文件存储集群中的 API 组件 {{ $labels.service }} 未运行，文件管理网络异常，文件存储网络异常，或文件控制器状态为未运行。"}],"impacts":[{"locale":"en-US","str":"The control service or the storage service of the file storage cluster is affected."},{"locale":"zh-CN","str":"文件存储集群的管控服务和（或）存储服务受到影响。"}],"solutions":[{"locale":"en-US","str":"Check the file controller's status and the network connectivity, or contact our technical support for assistance."},{"locale":"zh-CN","str":"检查文件控制器的运行状态、网络连接状态，或联系售后技术支持。"}]},{"name":"cluster_sfs_components_are_unavailable","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"for":"30s","interval":"15s","query_tmpl":"(sfs_operator_cluster_services_unavailable{service=~\"sfs-manager|sfs-cloud-provider\"} == 1 and ignoring(service) sfs_operator_cluster_services_unavailable{service=\"etcd\"} == 0 and ignoring(service) sfs_operator_cluster_services_unavailable{service=\"k8s-api-server\"} == 0) > {{ .threshold }}"},"metric_descriptor":{"is_boolean":true},"messages":[{"locale":"en-US","str":"The file service component {{ $labels.service }} in the file storage cluster {{ $labels.sfscluster }} is abnormal."},{"locale":"zh-CN","str":"文件存储集群 {{ $labels.sfscluster }} 中的文件服务组件 {{ $labels.service }} 状态异常。"}],"causes":[{"locale":"en-US","str":"The file service component {{ $labels.service }} in the file storage cluster is not running, or the file management network is abnormal."},{"locale":"zh-CN","str":"文件存储集群中的文件服务组件 {{ $labels.service }} 未运行，或文件管理网络异常。"}],"impacts":[{"locale":"en-US","str":"The control service of the file storage cluster is affected."},{"locale":"zh-CN","str":"文件存储集群的管控服务受到影响。"}],"solutions":[{"locale":"en-US","str":"Check the network connectivity, or contact our technical support for assistance."},{"locale":"zh-CN","str":"检查网络连接状态，或联系售后技术支持。"}]},{"name":"fsc_os_volume_pinning_not_enabled","type":"METRIC","default_thresholds":[{"severity":"CRITICAL","value":"0"}],"thresholds":[{"severity":"CRITICAL","value":"0"}],"metric_validator":{"interval":"15s","for":"30s","query_tmpl":"sfs_operator_fsc_os_volume_pinning_not_enabled > {{ .threshold }}"},"metric_descriptor":{"is_boolean":true},"messages":[{"locale":"en-US","str":"The system disk {{ $labels.volume_uuid }} of the file controller {{ $labels.fsc }} in the file storage cluster {{ $labels.sfscluster }} does not have volume pinning enabled."},{"locale":"zh-CN","str":"文件存储集群 {{ $labels.sfscluster }} 的文件控制器 {{ $labels.fsc }} 的系统盘 {{ $labels.volume_uuid }} 未启用常驻缓存。"}],"causes":[{"locale":"en-US","str":"The system disk of the file controller does not have volume pinning enabled."},{"locale":"zh-CN","str":"文件控制器的系统盘未启用常驻缓存。"}],"impacts":[{"locale":"en-US","str":"The control service on the file storage cluster might be affected during cache breakdown."},{"locale":"zh-CN","str":"文件存储集群的管控服务可能会在缓存击穿时受到影响。"}],"solutions":[{"locale":"en-US","str":"Enable volume pinning for the system disk of the corresponding file controller."},{"locale":"zh-CN","str":"为相应的文件控制器系统盘启用常驻缓存。"}]}],"instances":[{"url":"http://10.0.20.2/admin/observability/agent","info":{"service_name":"CloudTower","vm_name":"cloudtower"}}]}]},"query":"mutation updateObservabilityConnectedSystemServices($ovm_name: String!, $connected_system_services: [UpdateObservabilityConnectedSystemServiceInput!]!) {\n  updateObservabilityConnectedSystemServices(ovm_name: $ovm_name, connected_system_services: $connected_system_services) {\n    connected_system_services {\n      id\n      type\n      status\n      system_service {\n        id\n        name\n        version\n        __typename\n      }\n      instances {\n        state\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应
  {
    "data": {
        "updateObservabilityConnectedSystemServices": {
            "connected_system_services": [
                {
                    "id": "37KWbxlRh2aGU8mb7N8bLwqZ6jb",
                    "type": "CLOUDTOWER",
                    "status": "INSTALLING",
                    "system_service": {
                        "id": "CLOUDTOWER",
                        "name": "CloudTower",
                        "version": "4.7.1",
                        "__typename": "ObservabilityConnectedSystemServiceInfo"
                    },
                    "instances": [
                        {
                            "state": "STATE_UNSPECIFIED",
                            "__typename": "ObservabilityConnectedSystemServiceInstance"
                        }
                    ],
                    "__typename": "ObservabilityConnectedSystemService"
                }
            ],
            "__typename": "ObservabilityConnectedSystemServices"
        }
    }
}



  ## 部署备份
  
  ### 初始化上传备份安装包
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  content-type
  application/json
  cookie
  path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiUo

  载荷
  {"operationName":"createUploadTask","variables":{"data":{"status":"INITIALIZING","current_chunk":1,"chunk_size":4194304,"resource_type":"CLOUDTOWER_APPLICATION_PACKAGE","size":426394976,"args":{"name":"smtx-backup-dr-x86_64-2.2.1.tar.gz","package_name":"iomesh-backup"},"started_at":"2025-12-26T10:16:22.323Z"}},"query":"mutation createUploadTask($data: UploadTaskCreateInput!) {\n  createUploadTask(data: $data) {\n    id\n    current_chunk\n    chunk_size\n    __typename\n  }\n}\n"}

  响应
  {
    "data": {
        "createUploadTask": {
            "id": "cmjmpvci00io009585faip23e",
            "current_chunk": 1,
            "chunk_size": 4194304,
            "__typename": "UploadTask"
        }
    }
  }

  ### 上传备份安装包
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  header
  content-length
  4195101
  content-type
  multipart/form-data; boundary=----WebKitFormBoundaryWEf45EzjLT4tLzca
  cookie
  path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiU

  载荷（upload_task_id":"cmjmpvci00io009585faip23e"是上一步返回的id，current_chunk":42表示上传第42块数据）

  ------WebKitFormBoundaryQcfVBpzaWNBlYbLt
  Content-Disposition: form-data; name="operations"

  {"operationName":"uploadCloudTowerApplicationPackage","variables":{"data":{"upload_task_id":"cmjmpvci00io009585faip23e","file":null,"current_chunk":42}},"query":"mutation uploadCloudTowerApplicationPackage($data: UploadCloudTowerApplicationPackageInput!) {\n  uploadCloudTowerApplicationPackage(data: $data) {\n    id\n    status\n    current_chunk\n    chunk_size\n    __typename\n  }\n}\n"}
  ------WebKitFormBoundaryQcfVBpzaWNBlYbLt
  Content-Disposition: form-data; name="map"

  {"1":["variables.data.file"]}
  ------WebKitFormBoundaryQcfVBpzaWNBlYbLt
  Content-Disposition: form-data; name="1"; filename="blob"
  Content-Type: application/octet-stream

  /_hr®%n¡8¿®­E
  -¼ÁIÚucûñXÇSä!
  æ&n?Eòóöøå¯º~!Ñ -òh.ÎPÙT\,b¢-Ó{#VA¶¿Ó«wÅÛÉ«üÁIøPÚñË\z1éõ±?·h2Je±æ¥â#ä¥àç^*¦çù^X<%aT2ô`êTÔî¸5ö@cµdgöã^`gã¿MÑ²C·Jï¦4%-ôü×ÐGvÀ-¤.!EZFµØ.Û(rýÇ^·­9²´AÖ?¾Ãíld¥èaÍÅna?Ï~Nö½Ô½å¾Åô{|3V8±ÒûÅßQÎ÷/E<ÌÆqzÓdjÂ8S¢{ÊæykA¦åkÔÚÛ|>¿ÐÐ³RI'à5Yaß¸ÈÉ <þAÏEPæüÌ×|[k2¼ÛJ/UOD>õ8ßï«çße?©â¾oÄ­ÁÁô1x¶=DôÅ¤ôBå
  }nnë(Ñ·ñØ"÷²¤?#u	¡zî,²°%oxK¨»v_ÌÕ[Y§éÁ¯.µÖùÐJþ´Ö aüÑ-«í©d|Âµ±k

  响应
  {
    "data": {
        "uploadCloudTowerApplicationPackage": {
            "id": "cmjmpvci00io009585faip23e",
            "status": "UPLOADING",
            "current_chunk": 42,
            "chunk_size": 4194304,
            "__typename": "UploadTask"
        }
    }
  }


  最后一个分片上传完成后的响应，当status变为SUCCESSED表示上传完成
  {
    "data": {
        "uploadCloudTowerApplicationPackage": {
            "id": "cmjmuex5t13fu0958tfpuyh88",
            "status": "SUCCESSED",
            "current_chunk": 102,
            "chunk_size": 4194304,
            "__typename": "UploadTask"
        }
    }
}


  ### 查询安装包状态
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  cookie
  path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiUo

  载荷
  {"operationName":"cloudTowerApplicationPackages","variables":{"skip":0,"first":50,"where":{"AND":[{"name":"iomesh-backup"}]}},"query":"query cloudTowerApplicationPackages($where: CloudTowerApplicationPackageWhereInput, $orderBy: CloudTowerApplicationPackageOrderByInput, $skip: Int, $first: Int) {\n  cloudTowerApplicationPackages(where: $where, orderBy: $orderBy, skip: $skip, first: $first) {\n    id\n    filename\n    version\n    architecture\n    __typename\n  }\n  cloudTowerApplicationPackagesConnection(where: $where) {\n    aggregate {\n      count\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应（返回的id字段即为安装包ID，version是安装包版本，需要和本地匹配）
  {
    "data": {
        "cloudTowerApplicationPackages": [
            {
                "id": "cmjmpwgfw0k230958mpmjnmko",
                "filename": "smtx-backup-dr-x86_64-2.2.1.tar.gz",
                "version": "2.2.1",
                "architecture": "X86_64",
                "__typename": "CloudTowerApplicationPackage"
            }
        ],
        "cloudTowerApplicationPackagesConnection": {
            "aggregate": {
                "count": 1,
                "__typename": "AggregateCloudTowerApplicationPackage"
            },
            "__typename": "CloudTowerApplicationPackageConnection"
        }
    }
  }

  
  ### 创建备份存储网络
  部署之前需要在存储交换机上创建一个用于备份的存储网络

  #### 先查询虚拟交换机包含vDS-Storage字样的交换机ID

  请求网址
  https://10.0.20.2/v2/api/get-vdses
  请求方法
  POST

  header
  Authorization:eyJhbGciOiJIUzI1NiJ9.Y21qbW43dzNtMDM3aDA5NTgydzk4d3p2YQ.CU9uQTLbT0IE0C6gsmoMwzC61ivDs3g6OpxSpoFZKmc

  响应（需要获取包含vDS-Storage字样的交换机ID，"id": "cmjmn852w02c40958g9cpgt97",）
  [
    {
        "bond_mode": "active-backup",
        "cluster": {
            "id": "cmjmn817t03a00958p6jfr3m1",
            "name": "CN-BJ-SMTX-Prod-Cls01"
        },
        "entityAsyncStatus": null,
        "everoute_cluster": null,
        "id": "cmjmn852w02c2095826rkcngk",
        "internal": false,
        "labels": [],
        "local_id": "d9ec09a7-4a1b-494f-8ab1-32a6369f934a_797f0b49-c008-479a-b46a-c0460b95191e",
        "name": "vDS-Prod-Network",
        "nics": [
            {
                "id": "cmjmn82xy01yr0958d1by4e5e",
                "name": "ens257"
            },
            {
                "id": "cmjmn82zb020j0958ynw034rj",
                "name": "ens225"
            },
            {
                "id": "cmjmn82zd020m09587lhixo5l",
                "name": "ens225"
            },
            {
                "id": "cmjmn82zd020n0958thz02r6i",
                "name": "ens257"
            },
            {
                "id": "cmjmn831d022l09583u0x7g53",
                "name": "ens225"
            },
            {
                "id": "cmjmn834j024i09588hvayvax",
                "name": "ens257"
            },
            {
                "id": "cmjmn834j024j095818npug6i",
                "name": "ens225"
            },
            {
                "id": "cmjmn834l024k0958jbc6oosb",
                "name": "ens257"
            }
        ],
        "ovsbr_name": "ovsbr-4231kycbp",
        "type": "VM",
        "vlans": [
            {
                "id": "cmjmn857t000a109u5rk5dvva",
                "name": "VLAN-1120"
            },
            {
                "id": "cmjmn857t000b109uwcpxd5r1",
                "name": "VLAN-1126"
            },
            {
                "id": "cmjmn857u000c109uoivtxoxi",
                "name": "VLAN-1122"
            },
            {
                "id": "cmjmn857u000d109udgpia0s1",
                "name": "VLAN-1121"
            },
            {
                "id": "cmjmn857u000e109umxumvnu1",
                "name": "VLAN-1125"
            },
            {
                "id": "cmjmn857u000f109u3pk241yt",
                "name": "VLAN-1124"
            },
            {
                "id": "cmjmn857u000g109upvau6v5s",
                "name": "VLAN-1127"
            },
            {
                "id": "cmjmn857u000h109ug9n6fes4",
                "name": "VLAN-1123"
            },
            {
                "id": "cmjmn858f000i109u46bprtb6",
                "name": "VLAN-1128"
            },
            {
                "id": "cmjmn858k000j109ua9kvt1g1",
                "name": "VLAN-1129"
            },
            {
                "id": "cmjmn858k000k109ujtugbvwr",
                "name": "VLAN-1130"
            }
        ],
        "vlans_num": 11,
        "work_mode": "single"
    },
    {
        "bond_mode": "",
        "cluster": {
            "id": "cmjmn817t03a00958p6jfr3m1",
            "name": "CN-BJ-SMTX-Prod-Cls01"
        },
        "entityAsyncStatus": null,
        "everoute_cluster": null,
        "id": "cmjmn852w02c30958y7etd8ij",
        "internal": true,
        "labels": [],
        "local_id": "d9ec09a7-4a1b-494f-8ab1-32a6369f934a_dc51b1ca-7557-476c-9755-6214ca86e470",
        "name": "vds-ovsbr-internal",
        "nics": [],
        "ovsbr_name": "ovsbr-internal",
        "type": "VM",
        "vlans": [
            {
                "id": "cmjmn858m000m109u2ospw3g6",
                "name": "ovsbr-internal-default-network"
            }
        ],
        "vlans_num": 1,
        "work_mode": "single"
    },
    {
        "bond_mode": "active-backup",
        "cluster": {
            "id": "cmjmn817t03a00958p6jfr3m1",
            "name": "CN-BJ-SMTX-Prod-Cls01"
        },
        "entityAsyncStatus": null,
        "everoute_cluster": null,
        "id": "cmjmn852w02c40958g9cpgt97",
        "internal": false,
        "labels": [],
        "local_id": "d9ec09a7-4a1b-494f-8ab1-32a6369f934a_38909e6c-59d9-4e59-a21d-f415b0e42b2a",
        "name": "vDS-Storage-Network",
        "nics": [
            {
                "id": "cmjmn82xv01yj0958nltv6psc",
                "name": "ens256"
            },
            {
                "id": "cmjmn82xw01yk0958mltgnek2",
                "name": "ens161"
            },
            {
                "id": "cmjmn82zk020s0958od3c212p",
                "name": "ens256"
            },
            {
                "id": "cmjmn831c022j0958ab9dbex4",
                "name": "ens161"
            },
            {
                "id": "cmjmn831d022k09588rr2d466",
                "name": "ens256"
            },
            {
                "id": "cmjmn834f024g0958cplyx1ca",
                "name": "ens161"
            },
            {
                "id": "cmjmn837v025n0958c8jxx1el",
                "name": "ens161"
            },
            {
                "id": "cmjmn837v025o0958xxtyy29v",
                "name": "ens256"
            }
        ],
        "ovsbr_name": "ovsbr-7j7qtrvsm",
        "type": "VM",
        "vlans": [
            {
                "id": "cmjmn857s0009109u4sl2icu5",
                "name": "storage-network"
            }
        ],
        "vlans_num": 1,
        "work_mode": "single"
    },
    {
        "bond_mode": "active-backup",
        "cluster": {
            "id": "cmjmn817t03a00958p6jfr3m1",
            "name": "CN-BJ-SMTX-Prod-Cls01"
        },
        "entityAsyncStatus": null,
        "everoute_cluster": null,
        "id": "cmjmn852w02c509589kcitqu1",
        "internal": false,
        "labels": [],
        "local_id": "d9ec09a7-4a1b-494f-8ab1-32a6369f934a_53116410-db6b-49c7-b77d-255063067cb9",
        "name": "vDS-MgMt-Network",
        "nics": [
            {
                "id": "cmjmn82xx01yn095858vhzg6l",
                "name": "ens224"
            },
            {
                "id": "cmjmn82xx01yo0958rhjrkt0q",
                "name": "ens192"
            },
            {
                "id": "cmjmn82zb020i095811kbene5",
                "name": "ens224"
            },
            {
                "id": "cmjmn82zc020k0958suq44nad",
                "name": "ens192"
            },
            {
                "id": "cmjmn831f022n09581n7eavpv",
                "name": "ens224"
            },
            {
                "id": "cmjmn831f022o0958jjxmxl3i",
                "name": "ens192"
            },
            {
                "id": "cmjmn8358024r0958u1yqy4tf",
                "name": "ens224"
            },
            {
                "id": "cmjmn835d024t095815wdavxf",
                "name": "ens192"
            }
        ],
        "ovsbr_name": "ovsbr-c9d6xjuzp",
        "type": "VM",
        "vlans": [
            {
                "id": "cmjmn857s0008109uo39kdcuz",
                "name": "mgt-network"
            },
            {
                "id": "cmjmn858l000l109usa2uhc64",
                "name": "default"
            }
        ],
        "vlans_num": 2,
        "work_mode": "single"
    }
  ]

  #### 创建备份存储网络
  在存储交换机上创建一个用于备份的存储网络
  请求网址
  https://10.0.20.2/v2/api/create-vm-vlan
  请求方法
  POST
  header
  Authorization:eyJhbGciOiJIUzI1NiJ9.Y21qbW43dzNtMDM3aDA5NTgydzk4d3p2YQ.CU9uQTLbT0IE0C6gsmoMwzC61ivDs3g6OpxSpoFZKmc

   载荷（vds_id字段是上一步查询到的包含vDS-Storage字样的交换机ID，name字段是固定值，vlan_id字段是固定值）
  [
    {
      "vds_id": "cmjmn852w02c40958g9cpgt97",
      "name": "name-string"
    }
  ]

  响应（返回的id字段即为新建的用于备份服务的存储网络UUID，后续部署需要用该UUID）
  [
    {
        "data": {
            "id": "cmjms8zak0tm40958f422tc05",
            "local_id": "74d3f299-d217-4b62-bb8c-5bbc6309274f",
            "name": "name-string",
            "type": "VM",
            "vlan_id": 0,
            "gateway_ip": null,
            "subnetmask": null,
            "mode_type": "VLAN_ACCESS",
            "entityAsyncStatus": "CREATING",
            "gateway_subnetmask": null,
            "qos_min_bandwidth": null,
            "qos_max_bandwidth": null,
            "qos_priority": null,
            "qos_burst": null,
            "network_ids": [
                "0"
            ],
            "vds": {
                "id": "cmjmn852w02c40958g9cpgt97",
                "name": "vDS-Storage-Network"
            },
            "labels": []
        },
        "task_id": "cmjms8zat08lm7tudhsis2ry8"
    }
  ]


  ### 进行备份服务部署

  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  cookie
  path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiUo

  载荷
    (
    注意application.targetPackage字段的值是上一步返回的安装包ID,
    "storage_network_type": "NEW_NIC",  表示使用新建的存储网络，
    "backup_network_type": "MANAGEMENT",  表示使用管理网络作为备份网络，
    "management_network_gateway": "10.0.20.1",  表示管理网络网关，来源自规划表解析结果
    "management_network_ip": "10.0.20.4", 表示管理网络IP，来源自规划表解析结果
    "management_network_subnet_mask": "255.255.255.0", 表示管理网络子网掩码，来源自规划表解析结果
    "management_network_vlan": "cmjmn858l000l109usa2uhc64", 表示管理网络UUID，来源自查询网络接口
    "storage_network_ip": "10.0.21.4", 表示存储网络IP，来源自规划表解析结果
    "storage_network_subnet_mask": "255.255.255.0", 表示存储网络子网掩码，来源自规划表解析结果
    "storage_network_vlan": "cmjmn857u000d109udgpia0s1", 表示存储网络UUID，来源自查询网络接口
    "backup_network_gateway": "10.0.20.1", 当前使用管理网络作为备份网络时，备份网络网关和管理网络网关一致
    "backup_network_ip": "10.0.20.4", 当前使用管理网络作为备份网络时，备份网络IP和管理网络IP一致
    "backup_network_subnet_mask": "255.255.255.0", 当前使用管理网络作为备份网络时，备份网络子网掩码和管理网络子网掩码一致
    "backup_network_vlan": "cmjmn858l000l109usa2uhc64" , 当前使用管理网络作为备份网络时，备份网络UUID和管理网络UUID一致
    running_cluster字段是部署备份服务的集群ID，
    running_host字段是部署备份服务的主机ID，设置为AUTO_SCHEDULE让系统自动选择主机

    )

  {"operationName":"createBackupService","variables":{"data":{"name":"backup","entityAsyncStatus":"CREATING","status":"INSTALLING","application":{"create":{"instances":{"create":[]},"state":"INSTALLING","instanceStatuses":[],"name":"backup-bak","resourceVersion":0,"vmSpec":{},"targetPackage":"cmjmpwgfw0k230958mpmjnmko"}},"kube_config":"","storage_network_type":"NEW_NIC","backup_network_type":"MANAGEMENT","management_network_gateway":"10.0.20.1","management_network_ip":"10.0.20.4","management_network_subnet_mask":"255.255.255.0","management_network_vlan":"cmjmn858l000l109usa2uhc64","storage_network_ip":"10.0.21.4","storage_network_subnet_mask":"255.255.255.0","storage_network_vlan":"cmjmn857u000d109udgpia0s1","backup_network_gateway":"10.0.20.1","backup_network_ip":"10.0.20.4","backup_network_subnet_mask":"255.255.255.0","backup_network_vlan":"cmjmn858l000l109usa2uhc64"},"effect":{"running_cluster":"cmjmn817t03a00958p6jfr3m1","running_host":"AUTO_SCHEDULE"}},"query":"mutation createBackupService($data: BackupServiceCreateInput!, $effect: CreateBackupServiceEffect) {\n  createBackupService(data: $data, effect: $effect) {\n    id\n    __typename\n  }\n}\n"}

  响应（返回的id字段即为备份服务实例ID）
  {
    "data": {
        "createBackupService": {
            "id": "cmjmqhze006c47tudhqjjbrlf",
            "__typename": "BackupService"
        }
    }
  }


  ### 查询备份服务部署状态

  需要满足两个条件：

  1、backupService的status字段变成RUNNING
  请求网址
  https://10.0.20.2/api
  请求方法
  POST

  cookie
  path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiUo

  载荷
  {"operationName":"getBackupServices","variables":{},"query":"query getBackupServices($where: BackupServiceWhereInput) {\n  backupServices(where: $where) {\n    id\n    name\n    status\n    entityAsyncStatus\n    application {\n      id\n      package {\n        id\n        version\n        architecture\n        __typename\n      }\n      targetPackage\n      instanceStatuses\n      __typename\n    }\n    backup_clusters {\n      id\n      name\n      __typename\n    }\n    backup_plans {\n      id\n      name\n      __typename\n    }\n    running_vm {\n      id\n      status\n      cpu_usage\n      memory_usage\n      __typename\n    }\n    __typename\n  }\n}\n"}

  响应（状态为INSTALLING表示正在部署中,变成RUNNING表示部署完成）
  {
      "data": {
          "backupServices": [
              {
                  "id": "cmjmqhze006c47tudhqjjbrlf",
                  "name": "bak",
                  "status": "INSTALLING",
                  "entityAsyncStatus": "CREATING",
                  "application": {
                      "id": "cmjmqhze50m5j0958fp6tprio",
                      "package": {
                          "id": "cmjmpwgfw0k230958mpmjnmko",
                          "version": "2.2.1",
                          "architecture": "X86_64",
                          "__typename": "CloudTowerApplicationPackage"
                      },
                      "targetPackage": "cmjmpwgfw0k230958mpmjnmko",
                      "instanceStatuses": [
                          {
                              "applicationId": "cmjmqhze50m5j0958fp6tprio",
                              "vm": {
                                  "id": "cmjmqi2ap0m9v0958gbhlavdq",
                                  "name": "backup-bak-0",
                                  "cluster": "cmjmn817t03a00958p6jfr3m1",
                                  "cpu": 4,
                                  "memory": 17179869184,
                                  "vmStatus": "RUNNING",
                                  "storages": [
                                      {
                                          "size": 21474836480
                                      }
                                  ],
                                  "network": {
                                      "nics": [
                                          {
                                              "vlanId": "cmjmn858l000l109usa2uhc64",
                                              "ip": "10.0.20.4",
                                              "mask": "255.255.255.0",
                                              "gateway": "10.0.20.1"
                                          },
                                          {
                                              "vlanId": "cmjmn857u000d109udgpia0s1",
                                              "ip": "10.0.21.4",
                                              "mask": "255.255.255.0"
                                          }
                                      ]
                                  },
                                  "env": [
                                      {
                                          "name": "TOWER_ENDPOINT",
                                          "value": "10.0.20.2"
                                      },
                                      {
                                          "name": "TOWER_USERNAME",
                                          "value": "system-service"
                                      },
                                      {
                                          "name": "TOWER_PASSWORD",
                                          "value": "K5yt3hcjtUE4Teqe"
                                      },
                                      {
                                          "name": "TOWER_USER_SOURCE",
                                          "value": "LOCAL"
                                      },
                                      {
                                          "name": "BACKUP_SERVICE_ID",
                                          "value": "cmjmqhze006c47tudhqjjbrlf"
                                      },
                                      {
                                          "name": "SERVICE_OPTIONS",
                                          "value": "--enable-backup"
                                      },
                                      {
                                          "name": "SERVICE_NAMESPACE",
                                          "value": "iomesh-backup"
                                      },
                                      {
                                          "name": "GLOBAL_CONFIG_NAME",
                                          "value": "iomesh-backup-global-options"
                                      }
                                  ],
                                  "publicKeys": [
                                      "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC18BGUVj/yAKmOBqHakDS5uiQJi/tDa2s3mp3Cc2fKDaWQTRx6j7x66kTfT1Ppz1GknbEnKMoyg6EW2DAJfRx6aSFOF2Jkka8CsO3UPZvB/Af5ltMozqoUpzcWLr/kehgyAbkFoFD9dzuKzkn1s4P52Ey+1SB5cJToqFy1xpJDpdFDMPac5TMLwuX3vclRYcVp88o/cwsFKXWy3fcPbaBrnZxgPTx65TJx3h49s1MAaZJtNjbMw0VkE/g1gRHfY7kE0t9P/GDHuKKDquwKwUs1VoLqFtNe0HVy4hSd9HdlXCTjrqkjd1eOs8juMwMrjxN0f9LbEkw8AA6fKDdLPBsZ\n"
                                  ],
                                  "vmUsage": "BACKUP_CONTROLLER",
                                  "bootWithHost": true,
                                  "status": {
                                      "vmIps": [
                                          ""
                                      ],
                                      "message": "RUNNING"
                                  }
                              },
                              "package": {
                                  "id": "cmjmpwgfw0k230958mpmjnmko"
                              },
                              "status": {
                                  "phase": "RUNNING",
                                  "containerStatuses": [
                                      {
                                          "name": "launcher",
                                          "containerID": "dfffffeda76b6879f6ce887ff00bf43278484a38f3d84e8e47821bee93b649e7",
                                          "image": "registry.local/backup-dr/backup-launcher:2.2.1",
                                          "imageID": "sha256:3f77db9f87f8014b1706c8dfb685b92c19a889fb9a2081d4507ccc7cfea35920",
                                          "started": true,
                                          "ready": true,
                                          "state": {
                                              "running": {
                                                  "startedAt": "2025-12-26T10:36:35Z"
                                              }
                                          }
                                      }
                                  ],
                                  "error": {}
                              }
                          }
                      ],
                      "__typename": "CloudTowerApplication"
                  },
                  "backup_clusters": [],
                  "backup_plans": [],
                  "running_vm": null,
                  "__typename": "BackupService"
              }
          ]
      }
  }


2、任务状态完成
请求网址
https://10.0.20.2/v2/api/get-tasks
请求方法
post

header
Authorization: eyJhbGciOiJIUzI1NiJ9.Y21qbW43dzNtMDM3aDA5NTgydzk4d3p2YQ.CU9uQTLbT0IE0C6gsmoMwzC61ivDs3g6OpxSpoFZKmc

响应（具有Install Application backup-bak类似字样的任务描述对应的任务status变成SUCCESSED表示部署完成）
{
        "args": {},
        "cluster": null,
        "description": "Install Application backup-bak",
        "error_code": null,
        "error_message": null,
        "finished_at": "2025-12-26T10:36:35.000Z",
        "id": "cmjmqhzgo0m620958jsdlfmej",
        "internal": false,
        "key": null,
        "local_created_at": "2025-12-26T10:33:59.000Z",
        "progress": 1,
        "resource_id": "cmjmqhze50m5j0958fp6tprio",
        "resource_mutation": null,
        "resource_rollback_error": null,
        "resource_rollback_retry_count": null,
        "resource_rollbacked": null,
        "resource_type": "CloudTowerApplication",
        "snapshot": "{\"typename\":\"CloudTowerApplication\"}",
        "started_at": "2025-12-26T10:33:59.000Z",
        "status": "SUCCESSED",
        "steps": [
            {
                "current": 0,
                "finished": true,
                "key": "HANDLE_SCOS_VM",
                "per_second": 0,
                "total": null,
                "unit": null
            },
            {
                "current": 0,
                "finished": true,
                "key": "DEPLOY_PACKAGE",
                "per_second": 0,
                "total": null,
                "unit": null
            }
        ],
        "type": null,
        "user": {
            "id": "cmjmmuv2m01zz0958rg0pcywp",
            "name": "system service"
        }
    }



  ### 关联集群
请求网址
https://10.0.20.2/api
请求方法
POST

header
cookie
path=/; path=/; connect.sid=s%3Acmjmocflm03iz7tud2ayldusp.Ue%2B5hc4wvjviC1qh0uufqZpCT%2F3PlzWuTabpjbehiUo

载荷
（id":"cmjmqhze006c47tudhqjjbrlf"是上一步返回的备份服务实例ID，"cmjmn817t03a00958p6jfr3m1"是需要关联的集群ID）
{"operationName":"updateBackupService","variables":{"where":{"id":"cmjmqhze006c47tudhqjjbrlf"},"data":{"backup_clusters":{"set":[{"id":"cmjmn817t03a00958p6jfr3m1"}]}}},"query":"mutation updateBackupService($where: BackupServiceWhereUniqueInput!, $data: BackupServiceUpdateInput!) {\n  updateBackupService(where: $where, data: $data) {\n    id\n    name\n    __typename\n  }\n}\n"}

响应（返回的id字段即为备份服务实例ID，正常返回200表示关联成功）
{
    "data": {
        "updateBackupService": {
            "id": "cmjmqhze006c47tudhqjjbrlf",
            "name": "bak",
            "__typename": "BackupService"
        }
    }
}




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


  ## 查询集群ID
  请求网址
  https://your_tower_url/v2/api/get-clusters
  请求方法
  POST

  header
  Authorization: token（通过cloudtower登录接口获取的token）

  载荷（where部分的name字段填写集群名称，用于查询集群ID，来源与规划表）
  {
  "where": {
  "name": "CN-BJ-SMTX-Prod-Cls01"
  }
  }


  返回示例（"id": "cmjcow5a1038u09588mxmnop7" id字段即为集群ID，写入变量cluster_id）
  [
    {
        "access_write_compress_enabled": false,
        "allocated_prioritized_space": 0,
        "allocated_prioritized_space_usage": 0,
        "application_highest_version": "6.2.0",
        "applications": [],
        "architecture": "X86_64",
        "auto_converge": true,
        "commited_memory_bytes": 252527766528,
        "connect_state": "CONNECTED",
        "consistency_groups": [],
        "current_cpu_model": "EPYC",
        "data_reduction_ratio": 1,
        "data_reduction_saving": 0,
        "datacenters": [
            {
                "id": "cmjcow42b038609580wmbz3c6",
                "name": "C89-LAB"
            }
        ],
        "disconnected_date": null,
        "disconnected_reason": null,
        "dns": [
            "10.0.0.114",
            "10.0.0.1"
        ],
        "downgraded_prioritized_space": 0,
        "ecp_license": {
            "id": "cmjcowfye03gt0958q91rjoku"
        },
        "enable_tiering": true,
        "entityAsyncStatus": null,
        "everoute_cluster": null,
        "failure_data_space": 0,
        "has_metrox": true,
        "host_num": 4,
        "hosts": [
            {
                "id": "cmjcow6qr01r308582ljakeac",
                "management_ip": "10.0.20.12",
                "name": "BJ-SMTX-Prod-Node-02"
            },
            {
                "id": "cmjcow6qs01r40858555m1xyu",
                "management_ip": "10.0.20.13",
                "name": "BJ-SMTX-Prod-Node-03"
            },
            {
                "id": "cmjcow6qt01r508588kw4mvnt",
                "management_ip": "10.0.20.14",
                "name": "BJ-SMTX-Prod-Node-04"
            },
            {
                "id": "cmjcow6qt01r60858yx019goc",
                "management_ip": "10.0.20.11",
                "name": "BJ-SMTX-Prod-Node-01"
            }
        ],
        "hypervisor": "ELF",
        "id": "cmjcow5a1038u09588mxmnop7",
        "ip": "10.0.20.10",
        "is_all_flash": false,
        "iscsi_vip": null,
        "labels": [],
        "license_expire_date": "2026-01-18T08:42:44.000Z",
        "license_serial": "adb7c8ab-e868-4a75-b171-4a07bfa77c46",
        "license_sign_date": "2025-12-19T08:42:44.000Z",
        "license_type": "TRIAL",
        "local_id": "adb7c8ab-e868-4a75-b171-4a07bfa77c46",
        "logical_used_data_space": 128362217472,
        "maintenance_end_date": "1970-01-01T00:00:00.000Z",
        "maintenance_start_date": "1970-01-01T00:00:00.000Z",
        "management_vip": "10.0.20.10",
        "max_chunk_num": 255,
        "max_physical_data_capacity": 0,
        "max_physical_data_capacity_per_node": 140737488355328,
        "metro_availability_checklist": null,
        "mgt_gateway": "10.0.20.1",
        "mgt_netmask": "255.255.255.0",
        "migration_data_size": null,
        "migration_speed": null,
        "name": "CN-BJ-SMTX-Prod-Cls01",
        "no_performance_layer": false,
        "ntp_mode": "EXTERNAL",
        "ntp_servers": [
            "10.0.0.2",
            "ntp.c89.fun",
            "10.0.0.1"
        ],
        "nvme_over_rdma_enabled": false,
        "nvme_over_tcp_enabled": false,
        "nvmf_enabled": false,
        "overall_efficiency": 325.806695730855,
        "perf_allocated_data_space": 259922853888,
        "perf_failure_data_space": 0,
        "perf_total_data_capacity": 4329314451456,
        "perf_used_data_space": 259922853888,
        "perf_valid_data_space": 4329314451456,
        "planned_prioritized_space": 0,
        "pmem_enabled": false,
        "prio_space_percentage": 0,
        "provisioned_cpu_cores": 24,
        "provisioned_cpu_cores_for_active_vm": 24,
        "provisioned_for_active_vm_ratio": 0.421052631578947,
        "provisioned_memory_bytes": 54760833024,
        "provisioned_ratio": 0.421052631578947,
        "rdma_enabled": false,
        "recommended_cpu_models": [
            "EPYC"
        ],
        "recover_data_size": 0,
        "recover_speed": 0,
        "replica_capacity_only": false,
        "reserved_cpu_cores_for_system_service": 47,
        "running_vm_num": 2,
        "settings": {
            "id": "cmjcowfwz03gg09585pfhzim5"
        },
        "software_edition": "ENTERPRISE",
        "stopped_vm_num": 0,
        "stretch": false,
        "suspended_vm_num": 0,
        "total_cache_capacity": 5411642015744,
        "total_cpu_cores": 104,
        "total_cpu_hz": 257816000000,
        "total_cpu_models": [
            "host_passthrough",
            "Dhyana",
            "EPYC",
            "EPYC-IBPB",
            "Opteron_G3",
            "Opteron_G2",
            "Opteron_G1"
        ],
        "total_cpu_sockets": 5,
        "total_data_capacity": 9313481392128,
        "total_memory_bytes": 606261264384,
        "total_prio_volume_size": 0,
        "total_prio_volume_size_usage": 0,
        "type": "SMTX_OS",
        "upgrade_for_tiering": true,
        "upgrade_tool_version": "6.2.0-rc61",
        "used_cache_space": 262063783936,
        "used_cpu_hz": 35757095999.998,
        "used_data_space": 6373769216,
        "used_memory_bytes": 85899682460.363,
        "valid_cache_space": 5411642015744,
        "valid_data_space": 9313481392128,
        "vcenterAccount": null,
        "vdses": [
            {
                "id": "cmjcow91302ah0858psz7ukz0",
                "name": "vDS-MgMt-Network"
            },
            {
                "id": "cmjcow91302ai0858lvd17pe7",
                "name": "vDS-Storage-Network"
            },
            {
                "id": "cmjcow91402aj0858ddjg7riv",
                "name": "vDS-Prod-Network"
            },
            {
                "id": "cmjcow91402ak0858sakdmxoc",
                "name": "vds-ovsbr-internal"
            }
        ],
        "version": "6.2.0",
        "vhost_enabled": true,
        "vm_folders": [],
        "vm_num": 2,
        "vm_templates": [
            {
                "id": "cmjl05eda0b6p0958p51qm3l2",
                "name": "scos-kv5j86js6xp4nx5z4rhx"
            }
        ],
        "vms": [
            {
                "id": "cmjcowaqq006dqrqawpcs010o",
                "name": "cloudtower"
            },
            {
                "id": "cmjl060u70bdd0958vq8wg5q2",
                "name": "observability-obs-0"
            }
        ],
        "witness": null,
        "zones": []
    }
  ]




  ## 查询虚拟网络vnet_id
  
  请求网址
  https://your_tower_url/v2/api/get-vlans

  请求方法
  POST

  header
  Authorization: token（通过cloudtower登录接口获取的token）

  响应（id字段即为vnet_id，写入变量vnet_id）
      {
        "entityAsyncStatus": null,
        "gateway_ip": "",
        "gateway_subnetmask": "",
        "id": "cmjcow96r000lqrqalh84y2nd",
        "labels": [],
        "local_id": "adb7c8ab-e868-4a75-b171-4a07bfa77c46_c8a1e42d-e0f3-4d50-a190-53209a98f157",
        "mode_type": "VLAN_ACCESS",
        "name": "default",
        "network_ids": [
            "0"
        ],
        "qos_burst": null,
        "qos_max_bandwidth": null,
        "qos_min_bandwidth": null,
        "qos_priority": null,
        "subnetmask": "",
        "type": "VM",
        "vds": {
            "id": "cmjcow91302ah0858psz7ukz0",
            "name": "vDS-MgMt-Network"
        },
        "vlan_id": 0,
        "vm_nics": [
            {
                "id": "cmjcowar4006gqrqae6dv9b0z"
            },
            {
                "id": "cmjl0660e0011bwonzf7qch3o"
            }
        ]
    }




  ## 查询管理网络VDS及业务网络VDS






  ## 查询iso 的iscsi路径

  在创建cloudtower iso上传卷时，返回内容中的 image_path 字段即为该iso的iscsi路径








