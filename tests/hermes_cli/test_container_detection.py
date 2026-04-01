"""Tests for container/K8s environment detection across gateway and status modules."""

from types import SimpleNamespace

import hermes_cli.gateway as gateway_mod
import hermes_cli.status as status_mod


# =============================================================================
# Unit Tests: _is_container_env()
# =============================================================================


class TestIsContainerEnv:
    def test_returns_true_when_kubernetes_service_host_set(self, monkeypatch):
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.43.0.1")
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemctl")

        assert gateway_mod._is_container_env() is True

    def test_returns_true_when_systemctl_missing(self, monkeypatch):
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.setattr(
            "shutil.which",
            lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
        )

        assert gateway_mod._is_container_env() is True

    def test_returns_false_on_normal_linux(self, monkeypatch):
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/usr/bin/systemctl" if name == "systemctl" else None,
        )

        assert gateway_mod._is_container_env() is False

    def test_returns_true_when_both_k8s_and_no_systemctl(self, monkeypatch):
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.43.0.1")
        monkeypatch.setattr("shutil.which", lambda name: None)

        assert gateway_mod._is_container_env() is True


# =============================================================================
# Unit Tests: systemd_status() container early-return
# =============================================================================


class TestSystemdStatusContainer:
    def test_prints_running_in_container(self, monkeypatch, capsys):
        monkeypatch.setattr(gateway_mod, "_is_container_env", lambda: True)
        monkeypatch.setattr("gateway.status.is_gateway_running", lambda: True)

        gateway_mod.systemd_status()

        output = capsys.readouterr().out
        assert "running" in output
        assert "container/K8s" in output

    def test_prints_stopped_in_container(self, monkeypatch, capsys):
        monkeypatch.setattr(gateway_mod, "_is_container_env", lambda: True)
        monkeypatch.setattr("gateway.status.is_gateway_running", lambda: False)

        gateway_mod.systemd_status()

        output = capsys.readouterr().out
        assert "stopped" in output
        assert "container/K8s" in output

    def test_does_not_call_systemctl_in_container(self, monkeypatch, capsys):
        monkeypatch.setattr(gateway_mod, "_is_container_env", lambda: True)
        calls = []
        monkeypatch.setattr(
            gateway_mod.subprocess,
            "run",
            lambda cmd, **kw: calls.append(cmd),
        )

        gateway_mod.systemd_status()

        assert calls == [], "systemctl should not be called in container env"


# =============================================================================
# Unit Tests: _is_service_running() container path
# =============================================================================


class TestIsServiceRunningContainer:
    def test_returns_false_in_container_on_linux(self, monkeypatch):
        monkeypatch.setattr(gateway_mod, "is_linux", lambda: True)
        monkeypatch.setattr(gateway_mod, "_is_container_env", lambda: True)

        assert gateway_mod._is_service_running() is False

    def test_calls_systemctl_when_not_container_on_linux(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gateway_mod, "is_linux", lambda: True)
        monkeypatch.setattr(gateway_mod, "_is_container_env", lambda: False)

        # Both unit paths must exist for the systemctl call to happen
        user_unit = tmp_path / "user" / "hermes-gateway.service"
        user_unit.parent.mkdir(parents=True)
        user_unit.write_text("[Unit]\n")
        monkeypatch.setattr(
            gateway_mod,
            "get_systemd_unit_path",
            lambda system=False: user_unit if not system else tmp_path / "nope",
        )

        calls = []
        monkeypatch.setattr(
            gateway_mod.subprocess,
            "run",
            lambda cmd, **kw: (
                calls.append(cmd),
                SimpleNamespace(returncode=0, stdout="active\n", stderr=""),
            )[1],
        )

        result = gateway_mod._is_service_running()

        assert len(calls) > 0, "should have called systemctl"
        assert result is True


# =============================================================================
# E2E Tests: status.py container detection output
# =============================================================================


class TestStatusOutputContainer:
    def test_status_shows_running_in_container_on_linux(self, monkeypatch, capsys):
        """hermes status on Linux in a container shows running gateway."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.43.0.1")
        monkeypatch.setattr(
            "shutil.which",
            lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
        )
        monkeypatch.setattr("gateway.status.is_gateway_running", lambda: True)

        status_mod.show_status(SimpleNamespace(all=False, deep=False))

        output = capsys.readouterr().out
        assert "container/K8s" in output
        assert "running" in output

    def test_status_shows_stopped_in_container_on_linux(self, monkeypatch, capsys):
        """hermes status on Linux in a container shows stopped gateway."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.43.0.1")
        monkeypatch.setattr(
            "shutil.which",
            lambda name: None if name == "systemctl" else f"/usr/bin/{name}",
        )
        monkeypatch.setattr("gateway.status.is_gateway_running", lambda: False)

        status_mod.show_status(SimpleNamespace(all=False, deep=False))

        output = capsys.readouterr().out
        assert "container/K8s" in output
        assert "stopped" in output

    def test_status_shows_systemd_on_normal_linux(self, monkeypatch, capsys):
        """hermes status on normal Linux shows systemd manager."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/usr/bin/systemctl" if name == "systemctl" else None,
        )

        # Mock the systemctl call that checks gateway status
        monkeypatch.setattr(
            status_mod.subprocess,
            "run",
            lambda cmd, **kw: SimpleNamespace(
                returncode=0, stdout="active\n", stderr=""
            ),
        )

        status_mod.show_status(SimpleNamespace(all=False, deep=False))

        output = capsys.readouterr().out
        assert "systemd (user)" in output
        assert "container/K8s" not in output
