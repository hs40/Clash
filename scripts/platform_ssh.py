"""iStoreOS SSH 适配器：固定参数、固定命令、可注入 runner（S3）。

平台不读取私钥内容；认证由 Windows ssh-agent 完成。
"""

import shlex
import subprocess
from pathlib import Path

DEFAULT_HOST = "192.168.2.10"
DEFAULT_USER = "root"
DEFAULT_PORT = 22
DEFAULT_KNOWN_HOSTS = Path.home() / ".ssh" / "known_hosts"


class SshError(Exception):
    """SSH 连接、命令退出码或远端输出不符合契约。"""


def _check_remote_path(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise SshError("远端路径必须是绝对路径：%r" % (path,))
    if ".." in path.split("/"):
        raise SshError("远端路径不得包含 ..：%r" % path)
    if any(ch in path for ch in ("\x00", "\n", "\r")):
        raise SshError("远端路径包含控制字符")
    return path


class SshRunner:
    def __init__(self, host=DEFAULT_HOST, user=DEFAULT_USER, port=DEFAULT_PORT,
                 known_hosts=None, timeout=30, runner=None):
        if not isinstance(host, str) or not host.strip():
            raise SshError("host 不能为空")
        if not isinstance(user, str) or not user.strip():
            raise SshError("user 不能为空")
        self.host = host
        self.user = user
        self.port = int(port)
        self.known_hosts = Path(known_hosts or DEFAULT_KNOWN_HOSTS)
        self.timeout = timeout
        self._runner = runner or self._subprocess_runner

    def _subprocess_runner(self, args, input_text, timeout):
        # 必须用二进制 stdin/stdout：Windows 文本模式会把 \n 改写成 \r\n，
        # 导致上传文件与本地计算出的 LF 哈希不一致。
        data = None if input_text is None else input_text.encode("utf-8")
        try:
            result = subprocess.run(
                args,
                input=data,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SshError("SSH 执行失败：%s" % exc) from exc
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"),
        )

    def args(self, command, input_text=None):
        args = ["ssh"]
        if input_text is None:
            # 无输入的命令不继承本地 stdin，避免 ssh 在自动化终端里等待输入。
            args.append("-n")
        args.extend([
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=%s" % self.known_hosts,
            "-o", "ConnectTimeout=%d" % min(int(self.timeout), 30),
            "-p", str(self.port),
            "%s@%s" % (self.user, self.host),
            command,
        ])
        return args

    def run(self, command, input_text=None, timeout=None):
        if not isinstance(command, str) or not command.strip():
            raise SshError("远端命令不能为空")
        limit = timeout if timeout is not None else self.timeout
        result = self._runner(self.args(command, input_text), input_text, limit)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise SshError("远端命令失败（exit %d）：%s" % (result.returncode, detail))
        return result.stdout or ""

    def put_file(self, remote_path, content):
        _check_remote_path(remote_path)
        if not isinstance(content, str):
            raise SshError("上传内容必须是文本")
        command = "cat > %s" % shlex.quote(remote_path)
        self.run(command, input_text=content)
        return remote_path

    def read_file(self, remote_path):
        _check_remote_path(remote_path)
        return self.run("cat -- %s" % shlex.quote(remote_path))

    def exists(self, remote_path):
        _check_remote_path(remote_path)
        path = shlex.quote(remote_path)
        output = self.run("if [ -f %s ]; then echo yes; else echo no; fi" % path)
        return output.strip() == "yes"

    def sha256(self, remote_path):
        _check_remote_path(remote_path)
        output = self.run("sha256sum -- %s" % shlex.quote(remote_path)).strip()
        digest = output.split()[0] if output else ""
        if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
            raise SshError("远端 sha256sum 输出不可解析：%r" % output)
        return digest.lower()
