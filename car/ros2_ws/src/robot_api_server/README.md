# robot_api_server

## 职责
- 9100 权威写入口
- 负责会话、权限、命令接入与向 internal command socket 转发

## 输入
- HTTP / WS operator command

## 输出
- internal command socket、会话策略、命令 ACK

## 扩展点
- 新命令必须同步补权限、ACK、审计与前端 contract

## 禁改区
- 不要把 9001 只读 observer 面重新引回写路径

## 测试入口
- api / command / governance 相关测试
