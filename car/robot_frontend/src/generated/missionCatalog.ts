export const PRODUCT_MISSION_CATALOG = {
  "schemaVersion": "1.1.0",
  "deploymentModel": "single_robot_only",
  "defaultMissionId": "default_patrol",
  "catalogSource": "yaml_config",
  "catalogPath": "ros2_ws/src/robot_bringup/config/mission_catalog.yaml",
  "missions": {
    "default_patrol": {
      "missionId": "default_patrol",
      "title": "默认巡检",
      "routeName": "default",
      "taskProfile": "route_patrol",
      "autoTrack": true,
      "resumePolicy": "restart_route",
      "stages": [
        {
          "stageId": "route_execution",
          "title": "路径执行",
          "kind": "route",
          "routeName": "default",
          "expectedGoalCount": 0,
          "successMessage": "route_complete",
          "timeoutSec": 300.0,
          "supported": true,
          "owner": "robot_navigation",
          "startCondition": "mission_entered_or_previous_stage_completed",
          "completionCondition": "navigation_state=route_completed",
          "reason": null
        },
        {
          "stageId": "inspection_verification",
          "title": "巡检收尾",
          "kind": "verification",
          "routeName": null,
          "expectedGoalCount": 0,
          "successMessage": "mission_complete",
          "timeoutSec": 10.0,
          "verificationRules": {
            "requiredNavigationState": "route_completed",
            "minimumCompletedGoals": 1,
            "requirePositiveProgress": true,
            "requireRuntimeReady": true
          },
          "supported": true,
          "owner": "robot_decision",
          "startCondition": "previous_stage_completed",
          "completionCondition": "navigation_completion_and_runtime_health_verified",
          "reason": null
        }
      ],
      "operatorNotes": [
        "单机主线任务，进入 PATROL 后由 navigation 执行 route。",
        "可在产品接口中显式选择 missionId，但仍必须通过 9100 API facade 下发。"
      ]
    },
    "dock_then_patrol": {
      "missionId": "dock_then_patrol",
      "title": "回桩后巡检",
      "routeName": "docking_loop",
      "taskProfile": "dock_then_patrol",
      "autoTrack": false,
      "resumePolicy": "restart_stage",
      "stages": [
        {
          "stageId": "docking_route",
          "title": "回桩路径",
          "kind": "route",
          "routeName": "docking_loop",
          "expectedGoalCount": 0,
          "successMessage": "docking_complete",
          "timeoutSec": 240.0,
          "supported": true,
          "owner": "robot_navigation",
          "startCondition": "mission_entered_or_previous_stage_completed",
          "completionCondition": "navigation_state=route_completed",
          "reason": null
        },
        {
          "stageId": "patrol_route",
          "title": "巡检路径",
          "kind": "route",
          "routeName": "default",
          "expectedGoalCount": 0,
          "successMessage": "patrol_complete",
          "timeoutSec": 300.0,
          "supported": true,
          "owner": "robot_navigation",
          "startCondition": "mission_entered_or_previous_stage_completed",
          "completionCondition": "navigation_state=route_completed",
          "reason": null
        }
      ],
      "operatorNotes": [
        "复杂任务仍是单机内编排，不引入 fleet。"
      ]
    }
  }
} as const;
        export type GeneratedMissionCatalog = typeof PRODUCT_MISSION_CATALOG;
export type GeneratedMissionCatalogEntry = typeof PRODUCT_MISSION_CATALOG.missions[keyof typeof PRODUCT_MISSION_CATALOG.missions];
