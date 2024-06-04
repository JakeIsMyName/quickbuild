import argparse
import os
import sys
import time
import tomllib
from pathlib import Path

import util


def build(**kwargs):
    project_dir: Path
    cleanup: bool
    if os.path.isdir(kwargs["project"]):
        project_dir = Path(kwargs["project"])
        cleanup = False
    else:
        project_dir = util.clone_project(kwargs["project"], kwargs["branch"])
        cleanup = True
    cleanup = kwargs.get("cleanup", cleanup)

    jdk: str = kwargs.get("jdk", "")
    java = util.JDKIndex.latest()
    if jdk.isdigit():
        j = util.JDKIndex.get().get(int(jdk), None)
        if j:
            java = j
    elif os.path.isdir(jdk):
        metadata = util.get_java_metadata(jdk)
        if metadata:
            java = metadata[2]
    print(f"Using Java at {java}")

    util.build_project(Path(os.getcwd()), java, project_dir, kwargs["task"])
    if cleanup:
        util.color_print("Cleaning up project...", util.BlenderColors.HEADER)
        util.rmtree(project_dir)
        util.color_print("All done!", util.BlenderColors.OKGREEN)
        time.sleep(2)


def set_java_dir(**kwargs):
    util.JDKIndex.set_java_install_dir(kwargs["java-install-path"])


parser = argparse.ArgumentParser("quickbuild")
subparsers = parser.add_subparsers(dest="command")

parser_addjdk = subparsers.add_parser("set_java_dir")
parser_addjdk.add_argument("java-install-path", help="Path to directory containing Java installations.", type=str)

parser_build = subparsers.add_parser("build")
parser_build.add_argument("project", help="Link to Git repository you want to build.", type=str)
parser_build.add_argument("--branch", help="Name of the branch you want to build", type=str)
parser_build.add_argument("--jdk",
                          help="Version of Java to use for building."
                               "Takes either an integer which will specify the version to use from the Java install "
                               "directory, or a path to a Java installation. "
                               "Will use the latest version of Java in install directory if unspecified."
                          )

parser_build.add_argument("--task",
                          help="Gradle task to run for building the project."
                               "Will use \"build\" if not specified",
                          type=str
                          )
parser_build.add_argument("--cleanup",
                          help="Whether or not to delete the project after building."
                               "Default is true for remote projects, false for local projects",
                          type=bool
                          )

if __name__ == "__main__":
    args = vars(parser.parse_args())
    try:
        locals()[args.pop("command")](**args)
    except (Exception, KeyboardInterrupt) as e:
        status = util.Status
        if status.status:
            util.color_print("Caught exception, attempting cleanup!", util.BlenderColors.WARNING)
            if status.build_proc:
                print("Killing build process...")
                status.build_proc.kill()
            if status.temp_dir:
                print("Clearing temp...")
                util.rmtree(status.temp_dir)
        util.color_print(f"Process exiting at status; {status.status}", util.BlenderColors.WARNING)
        util.color_print(e, util.BlenderColors.FAIL)
