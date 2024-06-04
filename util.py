import json
import os
import stat
import subprocess
import tempfile
import time
import tomllib
from enum import StrEnum
from os import PathLike
from pathlib import Path


class Status:
    temp_dir: Path = None
    build_proc: subprocess.Popen[bytes] = None
    status: int = None


class JDKIndex:
    config_file_path = Path(os.getenv("LOCALAPPDATA")).joinpath("quickbuild.txt")
    java_install_dir = config_file_path.read_text() if config_file_path.is_file() else ""
    index: dict[int, Path] = {}

    @staticmethod
    def get() -> dict[int, Path]:
        if len(JDKIndex.index) == 0:
            JDKIndex.load_index()
        return JDKIndex.index

    @staticmethod
    def latest() -> Path:
        versions = list(JDKIndex.get().keys())
        versions.sort(reverse=True)
        latest = versions[0]
        print(f"Latest Java version is {latest}")
        return JDKIndex.index[latest]

    @staticmethod
    def set_java_install_dir(install_dir: str):
        if os.path.isdir(install_dir):
            with JDKIndex.config_file_path.open(mode="w") as config:
                config.write(install_dir)
            color_print("Successfully set Java install directory!", BlenderColors.OKGREEN)
            JDKIndex.load_index()
            print(JDKIndex.index)

    @staticmethod
    def load_index() -> None:
        JDKIndex.index = {}
        if JDKIndex.java_install_dir != "":
            for path in Path(JDKIndex.java_install_dir).iterdir():
                if path.is_dir():
                    metadata = get_java_metadata(path)
                    if metadata:
                        image_type, version, path = metadata
                        if image_type == "JDK":
                            JDKIndex.index[version] = path.resolve()
                        else:
                            color_print("Non-JDK Java binary found!", BlenderColors.FAIL)
        else:
            with open(JDKIndex.config_file_path, 'x') as config:
                config.write("C:\\Program Files\\Java")
                config.close()
            JDKIndex.load_index()


# sources:
# https://stackoverflow.com/a/287944
# https://svn.blender.org/svnroot/bf-blender/trunk/blender/build_files/scons/tools/bcolors.py
class BlenderColors(StrEnum):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def color_print(out: str, color: BlenderColors):
    print(f"{color}{out}{BlenderColors.ENDC}")


def quote(string: str | PathLike[str]) -> str:
    return f"\"{string}\""


def clone_project(project: str, branch: str | None) -> Path:
    color_print("Cloning remote project...", BlenderColors.HEADER)
    Status.status = "Cloning"
    tmp_dir = tempfile.mkdtemp()
    tmp_dirp = Path(tmp_dir)
    Status.temp_dir = tmp_dirp
    command = ["git", "clone", "--depth 1", quote(project), quote(tmp_dir)]
    if branch:
        command.extend(["--branch", branch])
    proc = subprocess.Popen(" ".join(command))
    proc.wait()
    color_print("Project cloned!", BlenderColors.OKCYAN)
    return tmp_dirp


def build_project(working_dir: Path, java_path: Path, project_dir: Path, task: str | None):
    color_print("Building project...", BlenderColors.HEADER)
    Status.status = "Building"
    output = working_dir.joinpath("quickbuild_out")
    gradle = project_dir.joinpath("gradle/wrapper/gradle-wrapper.jar")
    command = [
        quote(java_path),
        "-Xmx64m",
        "-Xms64m",
        "-classpath",
        quote(gradle),
        "org.gradle.wrapper.GradleWrapperMain",
        "--no-build-cache",
        "--no-daemon",
        task if task else "build",
        "-PbuildDir=%s" % quote(output)
    ]
    proc = subprocess.Popen(" ".join(command), cwd=project_dir)
    Status.build_proc = proc
    proc.wait()
    Status.build_proc = None
    time.sleep(2)
    color_print("Build finished!", BlenderColors.OKCYAN)


# source: https://stackoverflow.com/a/2656408
def rmtree(top: str | PathLike):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWRITE)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)


def get_java_metadata(path: str | PathLike) -> tuple[str, int, Path] | None:
    java_path = Path(path)
    err = "No error?"
    if not java_path.is_dir():
        err = "Given Java path is not a directory!"
    else:
        java_exe = java_path.joinpath("bin/java.exe")
        java_metadata = java_path.joinpath("release")
        if not java_exe.is_file():
            err = "Given Java path has no Java executable!"
        elif not java_metadata.is_file():
            err = "Given Java path is missing metadata!"
        else:
            data = tomllib.loads(java_metadata.read_text())
            split_ver = data["JAVA_VERSION"].split(".")
            ver: int
            if split_ver[0] == "1":
                ver = int(split_ver[1])
            else:
                ver = int(split_ver[0])
            return data.get("IMAGE_TYPE"), ver, java_exe
    color_print(err, BlenderColors.FAIL)
    return None
