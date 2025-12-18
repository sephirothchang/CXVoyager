# Workflow Flow (Mermaid)

下面是部署阶段的 mermaid 流程图（在支持 mermaid 的渲染器中可视化）：

```mermaid
flowchart LR
  %% High-level deployment workflow
  PREP["STEP 01\nPREPARE_PLAN_SHEET"] --> INIT["STEP 02\nINIT_CLUSTER"]
  INIT --> CONFIG["STEP 03\nCONFIG_CLUSTER"]
  CONFIG --> DEPLOY_CT["STEP 04\nDEPLOY_CLOUDTOWER"]
  DEPLOY_CT --> ATTACH["STEP 05\nATTACH_CLUSTER"]
  ATTACH --> CT_CFG["STEP 06\nCLOUDTOWER_CONFIG"]
  CT_CFG --> HEALTH["STEP 07\nCHECK_CLUSTER_HEALTHY"]

  %% App deployments can run after health check
  HEALTH --> APPS["Deploy Applications"]
  subgraph APPS_PARALLEL ["STEP 08-12\nAPPLICATION UPLOADS (parallel)"]
    OBS["STEP 08\nDEPLOY_OBS"]
    BAK["STEP 09\nDEPLOY_BAK"]
    ER["STEP 10\nDEPLOY_ER"]
    SFS["STEP 11\nDEPLOY_SFS"]
    SKS["STEP 12\nDEPLOY_SKS"]
  end
  APPS --> APPS_PARALLEL
  APPS_PARALLEL --> CREATE_VMS["STEP 13\nCREATE_TEST_VMS"]
  CREATE_VMS --> PERF["STEP 14\nPERF_RELIABILITY"]
  PERF --> CLEAN["STEP 15\nCLEANUP"]

  %% Optional parallel paths
  DEPLOY_CT -->|"if CloudTower already present"| ATTACH
  CONFIG -->|"may skip if cloudtower-only"| DEPLOY_CT
  style PREP fill:#f9f,stroke:#333,stroke-width:1px
  style CLEAN fill:#f2f2f2,stroke:#333,stroke-width:1px
```
