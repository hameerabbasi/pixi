from pathlib import Path
import tomllib

import tomli_w
from .common import verify_cli_command, ExitCode
import platform


def exec_extension(exe_name: str) -> str:
    if platform.system() == "Windows":
        return exe_name + ".bat"
    else:
        return exe_name


def test_sync_dependencies(pixi: Path, tmp_path: Path) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = """
    [envs.test]
    channels = ["conda-forge"]
    [envs.test.dependencies]
    python = "3.12"

    [envs.test.exposed]
    "python-injected" = "python"
    """
    parsed_toml = tomllib.loads(toml)
    manifest.write_text(toml)
    python_injected = tmp_path / "bin" / exec_extension("python-injected")

    # Test basic commands
    verify_cli_command([pixi, "global", "sync"], env=env)
    verify_cli_command([python_injected, "--version"], env=env, stdout_contains="3.12")
    verify_cli_command([python_injected, "-c", "import numpy"], ExitCode.FAILURE, env=env)

    # Add numpy
    parsed_toml["envs"]["test"]["dependencies"]["numpy"] = "*"
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command([pixi, "global", "sync"], env=env)
    verify_cli_command([python_injected, "-c", "import numpy"], env=env)

    # Remove numpy again
    del parsed_toml["envs"]["test"]["dependencies"]["numpy"]
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command([pixi, "global", "sync"], env=env)
    verify_cli_command([python_injected, "-c", "import numpy"], ExitCode.FAILURE, env=env)

    # Remove python
    del parsed_toml["envs"]["test"]["dependencies"]["python"]
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command(
        [pixi, "global", "sync"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains=["Could not find executable", "Failed to add executables for environment"],
    )


def test_sync_platform(pixi: Path, tmp_path: Path) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = """
    [envs.test]
    channels = ["conda-forge"]
    platform = "win-64"
    [envs.test.dependencies]
    binutils = "2.40"
    """
    parsed_toml = tomllib.loads(toml)
    manifest.write_text(toml)
    # Exists on win-64
    verify_cli_command([pixi, "global", "sync"], env=env)

    # Does not exist on osx-64
    parsed_toml["envs"]["test"]["platform"] = "osx-64"
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command(
        [pixi, "global", "sync"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="No candidates were found",
    )


def test_sync_change_expose(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    [envs.test.dependencies]
    dummy-a = "*"

    [envs.test.exposed]
    "dummy-a" = "dummy-a"
    """
    parsed_toml = tomllib.loads(toml)
    manifest.write_text(toml)
    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")

    # Test basic commands
    verify_cli_command([pixi, "global", "sync"], env=env)
    assert dummy_a.is_file()

    # Add another expose
    dummy_in_disguise_str = "dummy-in-disguise"
    dummy_in_disguise_file_name = exec_extension(dummy_in_disguise_str)
    dummy_in_disguise = tmp_path / "bin" / dummy_in_disguise_file_name
    parsed_toml["envs"]["test"]["exposed"][dummy_in_disguise_str] = "dummy-a"
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command([pixi, "global", "sync"], env=env)
    assert dummy_in_disguise.is_file()

    # Remove expose again
    del parsed_toml["envs"]["test"]["exposed"][dummy_in_disguise_str]
    manifest.write_text(tomli_w.dumps(parsed_toml))
    verify_cli_command([pixi, "global", "sync"], env=env)
    assert not dummy_in_disguise.is_file()


def test_sync_manually_remove_binary(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    [envs.test.dependencies]
    dummy-a = "*"

    [envs.test.exposed]
    "dummy-a" = "dummy-a"
    """
    manifest.write_text(toml)
    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")

    # Test basic commands
    verify_cli_command([pixi, "global", "sync"], env=env)
    assert dummy_a.is_file()

    # Remove binary manually
    dummy_a.unlink()

    # Binary is added again
    verify_cli_command([pixi, "global", "sync"], env=env)
    assert dummy_a.is_file()


def test_sync_migrate(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = f"""\
[envs.test]
channels = ["{dummy_channel_1}"]
dependencies = {{ dummy-a = "*", dummy-b = "*" }}
exposed = {{ dummy-1 = "dummy-a", dummy-2 = "dummy-a", dummy-3 = "dummy-b", dummy-4 = "dummy-b" }}
"""
    manifest.write_text(toml)
    verify_cli_command([pixi, "global", "sync"], env=env)

    # Test migration from existing environments
    original_manifest = manifest.read_text()
    manifest.unlink()
    manifests.rmdir()
    verify_cli_command([pixi, "global", "sync", "--assume-yes"], env=env)
    migrated_manifest = manifest.read_text()
    assert tomllib.loads(original_manifest) == tomllib.loads(migrated_manifest)


def test_expose_basic(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    dependencies = {{ dummy-a = "*" }}
    """
    manifest.write_text(toml)
    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy1 = tmp_path / "bin" / exec_extension("dummy1")
    dummy3 = tmp_path / "bin" / exec_extension("dummy3")

    # Add dummy-a with simple syntax
    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy-a"],
        ExitCode.SUCCESS,
        env=env,
    )
    assert dummy_a.is_file()

    # Add dummy1
    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy1=dummy-a"],
        env=env,
    )
    assert dummy1.is_file()

    # Add dummy3
    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy3=dummy-a"],
        env=env,
    )
    assert dummy3.is_file()

    # Remove dummy1
    verify_cli_command(
        [pixi, "global", "expose", "remove", "--environment=test", "dummy1"],
        env=env,
    )
    assert not dummy1.is_file()

    # Attempt to remove python2
    verify_cli_command(
        [pixi, "global", "expose", "remove", "--environment=test", "dummy2"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="The exposed name dummy2 doesn't exist",
    )


def test_expose_revert_working(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    original_toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    dependencies = {{ dummy-a = "*" }}
    """
    manifest.write_text(original_toml)

    # Attempt to add executable dummy-b that is not in our dependencies
    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy-b=dummy-b"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains=["Could not find executable dummy-b in", "test", "executables"],
    )

    # The TOML has been reverted to the original state
    assert manifest.read_text() == original_toml


def test_expose_revert_failure(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    original_toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    [envs.test.dependencies]
    dummy-a = "*"
    [envs.test.exposed]
    dummy1 = "dummy-b"
    """
    manifest.write_text(original_toml)

    # Attempt to add executable dummy-b that isn't in our dependencies
    # It should fail since the original manifest contains "dummy-b",
    # which is not in our dependencies
    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy2=dummyb"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="Could not add exposed mappings. Reverting also failed",
    )


def test_expose_preserves_table_format(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()
    manifest = manifests.joinpath("pixi-global.toml")
    original_toml = f"""
    [envs.test]
    channels = ["{dummy_channel_1}"]
    [env.test.dependencies]
    dummy-a = "*"
    [env.test.exposed]
    dummy-a = "dummy-a"
    """
    manifest.write_text(original_toml)

    verify_cli_command(
        [pixi, "global", "expose", "add", "--environment=test", "dummy-aa=dummy-aa"],
        ExitCode.FAILURE,
        env=env,
    )

    # The TOML has been reverted to the original state
    assert manifest.read_text() == original_toml


def test_install_adapts_manifest(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifest = manifests.joinpath("pixi-global.toml")

    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-a",
        ],
        env=env,
    )

    expected_manifest = f"""\
[envs.dummy-a]
channels = ["{dummy_channel_1}"]
dependencies = {{ dummy-a = "*" }}
exposed = {{ dummy-a = "dummy-a", dummy-aa = "dummy-aa" }}
"""
    actual_manifest = manifest.read_text()

    # Ensure that the manifest is correctly adapted
    assert actual_manifest == expected_manifest


def test_install_multiple_packages(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy_aa = tmp_path / "bin" / exec_extension("dummy-aa")
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    dummy_c = tmp_path / "bin" / exec_extension("dummy-c")

    # Install dummy-a and dummy-b, even though dummy-c is a dependency of dummy-b, it should not be exposed
    # All of dummy-a's and dummy-b's executables should be exposed though: 'dummy-a', 'dummy-aa' and 'dummy-b'
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-a",
            "dummy-b",
        ],
        env=env,
    )
    assert dummy_a.is_file()
    assert dummy_aa.is_file()
    assert dummy_b.is_file()
    assert not dummy_c.is_file()


def test_install_expose(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy_aa = tmp_path / "bin" / exec_extension("dummy-aa")
    dummy_c = tmp_path / "bin" / exec_extension("dummy-c")

    # Install dummy-a, even though dummy-c is a dependency, it should not be exposed
    # All of dummy-a's executables should be exposed though: 'dummy-a' and 'dummy-aa'
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-a",
        ],
        env=env,
    )
    assert dummy_a.is_file()
    assert dummy_aa.is_file()
    assert not dummy_c.is_file()

    # Install dummy-a, and expose dummy-c explicitly
    # Only dummy-c should now be exposed
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--expose",
            "dummy-c",
            "dummy-a",
        ],
        env=env,
    )
    assert not dummy_a.is_file()
    assert not dummy_aa.is_file()
    assert dummy_c.is_file()

    # Multiple mappings works as well
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--expose",
            "dummy-a",
            "--expose",
            "dummy-aa",
            "--expose",
            "dummy-c",
            "dummy-a",
        ],
        env=env,
    )
    assert dummy_a.is_file()
    assert dummy_aa.is_file()
    assert dummy_c.is_file()

    # Expose doesn't work with multiple environments
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--expose",
            "dummy-a",
            "dummy-a",
            "dummy-b",
        ],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="Cannot add exposed mappings for more than one environment",
    )

    # But it does work with multiple packages and a single environment
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--environment",
            "common-env",
            "--expose",
            "dummy-a",
            "dummy-a",
            "dummy-b",
        ],
        env=env,
    )


def test_install_only_reverts_failing(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    dummy_x = tmp_path / "bin" / exec_extension("dummy-x")

    # dummy-x is not part of dummy_channel_1
    verify_cli_command(
        [pixi, "global", "install", "--channel", dummy_channel_1, "dummy-a", "dummy-b", "dummy-x"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="No candidates were found for dummy-x",
    )

    # dummy-a, dummy-b should be installed, but not dummy-x
    assert dummy_a.is_file()
    assert dummy_b.is_file()
    assert not dummy_x.is_file()


def test_install_platform(pixi: Path, tmp_path: Path) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    # Exists on win-64
    verify_cli_command(
        [pixi, "global", "install", "--platform", "win-64", "binutils=2.40"],
        env=env,
    )

    # Does not exist on osx-64
    verify_cli_command(
        [pixi, "global", "install", "--platform", "osx-64", "binutils=2.40"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="No candidates were found",
    )


def test_install_channels(
    pixi: Path, tmp_path: Path, dummy_channel_1: str, dummy_channel_2: str
) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    dummy_x = tmp_path / "bin" / exec_extension("dummy-x")

    # Install dummy-b from dummy-channel-1
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-b",
        ],
        env=env,
    )
    assert dummy_b.is_file()

    # Install dummy-x from dummy-channel-2
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_2,
            "dummy-x",
        ],
        env=env,
    )
    assert dummy_x.is_file()

    # Install dummy-b and dummy-x from dummy-channel-1 and dummy-channel-2
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "--channel",
            dummy_channel_2,
            "dummy-b",
            "dummy-x",
        ],
        env=env,
    )
    assert dummy_b.is_file()
    assert dummy_x.is_file()


def test_install_multi_env_install(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    # Install dummy-a and dummy-b from dummy-channel-1 this will fail if both environment contains the same package as spec.
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-a",
            "dummy-b",
        ],
        env=env,
    )


def test_list(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    manifests = tmp_path.joinpath("manifests")
    manifests.mkdir()

    # Verify empty list
    verify_cli_command(
        [pixi, "global", "list"],
        env=env,
        stdout_contains="No global environments found.",
    )

    # Install dummy-b from dummy-channel-1
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-b==0.1.0",
            "dummy-a==0.1.0",
        ],
        env=env,
    )

    # Verify list with dummy-b
    verify_cli_command(
        [pixi, "global", "list"],
        env=env,
        stdout_contains=["dummy-b: 0.1.0", "dummy-a: 0.1.0", "dummy-a", "dummy-aa"],
    )


def test_uninstall(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    # Verify empty list
    verify_cli_command(
        [pixi, "global", "list"],
        env=env,
        stdout_contains="No global environments found.",
    )

    # Install dummy-b from dummy-channel-1
    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            dummy_channel_1,
            "dummy-a",
            "dummy-b",
            "dummy-c",
        ],
        env=env,
    )
    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy_aa = tmp_path / "bin" / exec_extension("dummy-aa")
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    dummy_c = tmp_path / "bin" / exec_extension("dummy-c")
    assert dummy_a.is_file()
    assert dummy_aa.is_file()
    assert dummy_b.is_file()
    assert dummy_c.is_file()

    # Uninstall dummy-b
    verify_cli_command(
        [pixi, "global", "uninstall", "dummy-a"],
        env=env,
    )
    assert not dummy_a.is_file()
    assert not dummy_aa.is_file()
    assert dummy_b.is_file()
    assert dummy_c.is_file()
    # Verify only the dummy-a environment is removed
    assert tmp_path.joinpath("envs", "dummy-b").is_dir()
    assert tmp_path.joinpath("envs", "dummy-c").is_dir()
    assert not tmp_path.joinpath("envs", "dummy-a").is_dir()

    # Uninstall dummy-b and dummy-c
    verify_cli_command(
        [pixi, "global", "uninstall", "dummy-b", "dummy-c"],
        env=env,
    )
    assert not dummy_a.is_file()
    assert not dummy_aa.is_file()
    assert not dummy_b.is_file()
    assert not dummy_c.is_file()

    # Verify empty list
    verify_cli_command(
        [pixi, "global", "list"],
        env=env,
        stdout_contains="No global environments found.",
    )

    # Uninstall non-existing package
    verify_cli_command(
        [pixi, "global", "uninstall", "dummy-a"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains=["not found", "dummy-a"],
    )


def test_uninstall_only_reverts_failing(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")

    verify_cli_command(
        [pixi, "global", "install", "--channel", dummy_channel_1, "dummy-a", "dummy-b"],
        env=env,
    )

    # We did not install dummy-c
    verify_cli_command(
        [pixi, "global", "uninstall", "dummy-a", "dummy-c"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="Environment 'dummy-c' not found in manifest",
    )

    # dummy-a has been removed but dummy-b is still there
    assert not dummy_a.is_file()
    assert not tmp_path.joinpath("envs", "dummy-a").is_dir()
    assert dummy_b.is_file()
    assert tmp_path.joinpath("envs", "dummy-b").is_dir()


def test_global_update_single_package(
    pixi: Path, tmp_path: Path, global_update_channel_1: str
) -> None:
    env = {"PIXI_HOME": str(tmp_path)}
    # Test update with no environments
    verify_cli_command(
        [pixi, "global", "update"],
        env=env,
    )

    # Test update of a single package
    verify_cli_command(
        [pixi, "global", "install", "--channel", global_update_channel_1, "package 0.1.0"],
        env=env,
    )
    # Replace the version with a "*"
    manifest = tmp_path.joinpath("manifests", "pixi-global.toml")
    manifest.write_text(manifest.read_text().replace("==0.1.0", "*"))
    verify_cli_command(
        [pixi, "global", "update", "package"],
        env=env,
    )
    package = tmp_path / "bin" / exec_extension("package")
    package0_1_0 = tmp_path / "bin" / exec_extension("package0.1.0")
    package0_2_0 = tmp_path / "bin" / exec_extension("package0.2.0")

    # After update be left with only the binary that was in both versions.
    assert package.is_file()
    assert not package0_1_0.is_file()
    # pixi global update doesn't add new exposed mappings
    assert not package0_2_0.is_file()


def test_global_update_all_packages(
    pixi: Path, tmp_path: Path, global_update_channel_1: str
) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    verify_cli_command(
        [
            pixi,
            "global",
            "install",
            "--channel",
            global_update_channel_1,
            "package2==0.1.0",
            "package==0.1.0",
        ],
        env=env,
    )

    package = tmp_path / "bin" / exec_extension("package")
    package0_1_0 = tmp_path / "bin" / exec_extension("package0.1.0")
    package0_2_0 = tmp_path / "bin" / exec_extension("package0.2.0")
    package2 = tmp_path / "bin" / exec_extension("package2")
    assert package2.is_file()
    assert package.is_file()
    assert package0_1_0.is_file()
    assert not package0_2_0.is_file()

    # Replace the version with a "*"
    manifest = tmp_path.joinpath("manifests", "pixi-global.toml")
    manifest.write_text(manifest.read_text().replace("==0.1.0", "*"))

    verify_cli_command(
        [pixi, "global", "update"],
        env=env,
    )
    assert package2.is_file()
    assert package.is_file()
    assert not package0_1_0.is_file()
    # After update be left with only the binary that was in both versions.
    assert not package0_2_0.is_file()

    # Check the manifest for removed binaries
    manifest_content = manifest.read_text()
    assert "package0.1.0" not in manifest_content
    assert "package0.2.0" not in manifest_content
    assert "package2" in manifest_content
    assert "package" in manifest_content

    # Check content of package2 file to be updated
    bin_file_package2 = tmp_path / "envs" / "package2" / "bin" / exec_extension("package2")
    assert "0.2.0" in bin_file_package2.read_text()


def test_auto_self_expose(pixi: Path, tmp_path: Path, non_self_expose_channel: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    # Install jupyter and expose it as 'jupyter'
    verify_cli_command(
        [pixi, "global", "install", "--channel", non_self_expose_channel, "jupyter"],
        env=env,
    )
    jupyter = tmp_path / "bin" / exec_extension("jupyter")
    assert jupyter.is_file()


def test_add(pixi: Path, tmp_path: Path, dummy_channel_1: str) -> None:
    env = {"PIXI_HOME": str(tmp_path)}

    # Cannot add package to environment that doesn't exist
    verify_cli_command(
        [pixi, "global", "add", "--environment", "dummy-a", "dummy-b"],
        ExitCode.FAILURE,
        env=env,
        stderr_contains="Environment dummy-a doesn't exist",
    )

    verify_cli_command(
        [pixi, "global", "install", "--channel", dummy_channel_1, "dummy-a"],
        env=env,
    )
    dummy_a = tmp_path / "bin" / exec_extension("dummy-a")
    assert dummy_a.is_file()

    verify_cli_command(
        [pixi, "global", "add", "--environment", "dummy-a", "dummy-b"],
        env=env,
        stderr_contains="Added package 'dummy-b",
    )
    # Make sure it doesn't expose a binary from this package
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    assert not dummy_b.is_file()

    verify_cli_command(
        [
            pixi,
            "global",
            "add",
            "--environment",
            "dummy-a",
            "dummy-b",
            "--expose",
            "dummy-b",
        ],
        env=env,
        stderr_contains=["Added executable 'dummy-b"],
    )
    # Make sure it now exposes the binary
    dummy_b = tmp_path / "bin" / exec_extension("dummy-b")
    assert dummy_b.is_file()