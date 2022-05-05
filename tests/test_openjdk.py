"""Tests of the OpenJDK base container."""
import pytest

from bci_tester.data import OPENJDK_11_CONTAINER
from bci_tester.data import OPENJDK_17_CONTAINER

CONTAINER_IMAGES = [
    OPENJDK_11_CONTAINER,
    OPENJDK_17_CONTAINER,
]


@pytest.mark.parametrize(
    "container,java_version",
    [
        pytest.param(cont, ver, marks=cont.marks)
        for cont, ver in (
            (OPENJDK_11_CONTAINER, "11"),
            (OPENJDK_17_CONTAINER, "17"),
        )
    ],
    indirect=["container"],
)
def test_jdk_version(container, java_version: str):
    """Check that the environment variable ``JAVA_VERSION`` is equal to the output
    of :command:`java --version`.

    """
    assert f"openjdk {java_version}" in container.connection.check_output(
        "java --version"
    )

    assert (
        container.connection.check_output("echo $JAVA_VERSION") == java_version
    )
