# 历史正常参考 C1 技术修复交付

独立于失败作业 180433，保留旧科学包、输出和提交锁。用户已经明确授权“修复问题，然后提交；提交”。固定 C1/P-DEVONLY、4CPU/16GiB/8小时/20GiB，源 DEV 门通过才评价一次 A/B；不训练，不自动科学重试。

构建：`python build_delivery.py --tshark /share/software/tshark-4.6.6/bin/tshark --package-seal <修复包CODE_MANIFEST的SHA256> --expected-tests <修复测试实测通过数>`。构建要求修复实现回执中的测试数一致，核完整代码及输入 SHA。大数据不复制；远端同 SHA 文件可复用，任何冲突停止且不覆盖。构建后运行 `python bind_transport.py` 将新 inventory SHA 和文件数固定进传输客户端与接收器。禁止在 inventory 构建后改动其中任何交付文件。

远端验收按授权回执的固定实测测试数验收，仍要求 Python3.11.11/NumPy2.0.1/Torch2.5.1、全部代码输入、材料 READY。submit_once 独占写锁后仅调用一次 sbatch，未知结果禁止重试。

新远端接收器端口18788；本地只读进度页18787。旧18785/18786保持独立。由 Codex 右侧打开进度页，确认实际工作进程后结束 AI 跟踪。
