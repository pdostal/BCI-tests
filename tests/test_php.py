from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Literal

import pytest
from pytest_container import container_from_pytest_param
from pytest_container import DerivedContainer
from pytest_container import OciRuntimeBase
from pytest_container.container import ContainerData
from pytest_container.container import ImageFormat
from pytest_container.container import PortForwarding
from pytest_container.pod import Pod
from pytest_container.pod import PodData

from bci_tester.data import PHP_8_APACHE
from bci_tester.data import PHP_8_CLI
from bci_tester.data import PHP_8_FPM


CONTAINER_IMAGES = [PHP_8_CLI, PHP_8_APACHE, PHP_8_FPM]

PHP_FLAVOR_T = Literal["apache", "fpm", "cli"]
CONTAINER_IMAGES_WITH_FLAVORS = [
    pytest.param(*t, marks=t[0].marks)
    for t in ((PHP_8_APACHE, "apache"), (PHP_8_FPM, "fpm"), (PHP_8_CLI, "cli"))
]
_PHP_MAJOR_VERSION = 8
_MEDIAWIKI_VERSION = "1.39.2"
_MEDIAWIKI_MAJOR_VERSION = ".".join(_MEDIAWIKI_VERSION.split(".")[:2])

MEDIAWIKI_APACHE_CONTAINER = DerivedContainer(
    base=container_from_pytest_param(PHP_8_APACHE),
    forwarded_ports=[PortForwarding(container_port=80)],
    image_format=ImageFormat.DOCKER,
    containerfile=f"""ENV MEDIAWIKI_VERSION={_MEDIAWIKI_VERSION}
ENV MEDIAWIKI_MAJOR_VERSION={_MEDIAWIKI_MAJOR_VERSION}"""
    + """
RUN set -e; zypper -n in $PHPIZE_DEPS oniguruma-devel libicu-devel gcc-c++ php8-sqlite php8-gd gzip && \
    for ext in mbstring intl fileinfo iconv calendar ctype dom; do \
        docker-php-ext-configure $ext; \
        docker-php-ext-install $ext; \
    done \
    && docker-php-source delete \
    && zypper -n rm $PHPIZE_DEPS oniguruma-devel libicu-devel gcc-c++ \
    && zypper -n clean && rm -rf /var/log/{zypp*,suseconnect*}

RUN set -euo pipefail; \
    zypper -n in tar; \
    curl -OLf "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    tar xvzf "mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    rm "mediawiki-${MEDIAWIKI_VERSION}.tar.gz"; \
    pushd "mediawiki-${MEDIAWIKI_VERSION}/"; mv * ..; popd; rmdir "mediawiki-${MEDIAWIKI_VERSION}"; \
    php maintenance/install.php --dbname mediawiki.db --dbtype sqlite --pass insecureAndAtLeast10CharsLong --scriptpath="" --server="http://localhost" test-wiki geeko; \
    chown --recursive wwwrun data; \
    zypper -n clean; rm -rf /var/log/{zypp*,suseconnect*}

HEALTHCHECK --interval=10s --timeout=1s --retries=10 CMD curl --fail http://localhost
EXPOSE 80
""",
)


MEDIAWIKI_FPM_CONTAINER = DerivedContainer(
    base=container_from_pytest_param(PHP_8_FPM),
    containerfile=f"""ENV MEDIAWIKI_VERSION={_MEDIAWIKI_VERSION}
ENV MEDIAWIKI_MAJOR_VERSION={_MEDIAWIKI_MAJOR_VERSION}"""
    + r"""
RUN set -eux; \
    zypper -n ref; \
    zypper -n up; \
    zypper -n in $PHPIZE_DEPS php8-pecl oniguruma-devel git \
		librsvg \
		ImageMagick \
		python3; # Required for SyntaxHighlighting

# Install the PHP extensions we need
RUN set -eux; \
    zypper -n in libicu-devel php8-mysql php8-sqlite; \
	docker-php-ext-install \
		calendar \
		intl \
                mbstring \
                opcache \
                iconv \
                ctype \
                fileinfo \
                dom ; \
	pecl install APCu-5.1.21; \
	docker-php-ext-enable apcu; \
	rm -r /tmp/pear


# set recommended PHP.ini settings
# see https://secure.php.net/manual/en/opcache.installation.php
RUN { \
		echo 'opcache.memory_consumption=128'; \
		echo 'opcache.interned_strings_buffer=8'; \
		echo 'opcache.max_accelerated_files=4000'; \
		echo 'opcache.revalidate_freq=60'; \
	} > /etc/php8/conf.d/opcache-recommended.ini

# SQLite Directory Setup
RUN set -eux; \
	mkdir -p data; \
	chown -R wwwrun data

# MediaWiki setup
RUN set -eux; \
    zypper -n in dirmngr gzip; \
	curl -fSL "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz" -o mediawiki.tar.gz; \
	curl -fSL "https://releases.wikimedia.org/mediawiki/${MEDIAWIKI_MAJOR_VERSION}/mediawiki-${MEDIAWIKI_VERSION}.tar.gz.sig" -o mediawiki.tar.gz.sig; \
	export GNUPGHOME="$(mktemp -d)"; \
        # gpg key from https://www.mediawiki.org/keys/keys.txt
	gpg --batch --keyserver keyserver.ubuntu.com --recv-keys \
		D7D6767D135A514BEB86E9BA75682B08E8A3FEC4 \
		441276E9CCD15F44F6D97D18C119E1A64D70938E \
		F7F780D82EBFB8A56556E7EE82403E59F9F8CD79 \
		1D98867E82982C8FE0ABC25F9B69B3109D3BB7B0 \
	; \
	gpg --batch --verify mediawiki.tar.gz.sig mediawiki.tar.gz; \
	tar -x --strip-components=1 -f mediawiki.tar.gz; \
	gpgconf --kill all; \
        rm -r "$GNUPGHOME" mediawiki.tar.gz.sig mediawiki.tar.gz; \
        chown -R wwwrun extensions skins cache images data; \
        php maintenance/install.php --dbname mediawiki.db --dbtype sqlite --pass insecureAndAtLeast10CharsLong --scriptpath="" --server="http://localhost" test-wiki geeko && \
        chown --recursive wwwrun data; \
	zypper -n rm dirmngr gzip;

CMD ["php-fpm"]
""",
)

NGINX_FPM_PROXY = DerivedContainer(
    base="registry.opensuse.org/opensuse/nginx",
    containerfile="""COPY tests/files/nginx.conf /etc/nginx/
COPY tests/files/fastcgi_params /etc/nginx/
""",
)

MEDIAWIKI_FPM_POD = Pod(
    containers=[MEDIAWIKI_FPM_CONTAINER, NGINX_FPM_PROXY],
    forwarded_ports=[PortForwarding(container_port=80)],
)


def test_install_phpize_deps(auto_container_per_test: ContainerData):
    auto_container_per_test.connection.run_expect(
        [0],
        "zypper -n in $PHPIZE_DEPS",
    )
    auto_container_per_test.connection.run_expect([0], "touch config.m4")
    auto_container_per_test.connection.run_expect([0], "phpize")


@dataclass
class PhpExtension:
    name: str
    extra_dependencies: List[str] = field(default_factory=list)
    configure_flags: str = ""


@pytest.mark.parametrize("extension", ["pcntl", "gd"])
def test_install_php_extension_via_script(
    auto_container_per_test: ContainerData, extension: str
):
    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-configure {extension}"
    )
    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-install {extension}"
    )

    assert (
        extension
        in auto_container_per_test.connection.run_expect([0], "php -m").stdout
    )


def test_install_multiple_extensions_via_script(
    auto_container_per_test: ContainerData,
) -> None:
    extensions = [
        "calendar",
        "intl",
        "mbstring",
        "opcache",
        "iconv",
        "ctype",
        "fileinfo",
        "dom",
    ]

    auto_container_per_test.connection.run_expect(
        [0], f"docker-php-ext-install {' '.join(extensions)}"
    )
    for ext in extensions:
        assert auto_container_per_test.connection.package(
            f"php{_PHP_MAJOR_VERSION}-{ext}"
        ).is_installed


@pytest.mark.parametrize("extension_name", ["gd"])
def test_zypper_install_php_extensions(
    auto_container_per_test: ContainerData, extension_name: str
):
    assert (
        extension_name
        not in auto_container_per_test.connection.run_expect(
            [0], "php -m"
        ).stdout
    )
    auto_container_per_test.connection.run_expect(
        [0], f"zypper -n in php{_PHP_MAJOR_VERSION}-{extension_name}"
    )
    assert (
        extension_name
        in auto_container_per_test.connection.run_expect([0], "php -m").stdout
    )


@pytest.mark.parametrize(
    "container_per_test,flavor",
    CONTAINER_IMAGES_WITH_FLAVORS,
    indirect=["container_per_test"],
)
def test_environment_variables(
    container_per_test: ContainerData, flavor: PHP_FLAVOR_T
):
    def get_env_var(env_var: str) -> str:
        return container_per_test.connection.run_expect(
            [0], f"echo ${env_var}"
        ).stdout.strip()

    php_pkg_version = container_per_test.connection.package(
        f"php{_PHP_MAJOR_VERSION}"
    ).version
    assert php_pkg_version == get_env_var("PHP_VERSION")

    assert container_per_test.connection.package(
        "php-composer2"
    ).version == get_env_var("COMPOSER_VERSION")

    php_ini_dir_path = get_env_var("PHP_INI_DIR")
    php_ini_dir = container_per_test.connection.file(php_ini_dir_path)
    assert php_ini_dir.exists and php_ini_dir.is_directory

    if flavor == "apache":
        apache_confdir = get_env_var("APACHE_CONFDIR")
        assert container_per_test.connection.file(apache_confdir).is_directory
        assert container_per_test.connection.file(
            f"{apache_confdir}/httpd.conf"
        ).is_file

        apache_envvars = get_env_var("APACHE_ENVVARS")
        assert container_per_test.connection.file(apache_envvars).is_file
        assert container_per_test.connection.run_expect(
            [0], f"source {apache_envvars}"
        )


@pytest.mark.parametrize("container_image", [PHP_8_CLI])
def test_cli_entry_point(
    container_image: DerivedContainer,
    container_runtime: OciRuntimeBase,
    host,
    pytestconfig: pytest.Config,
):
    container_image.prepare_container(pytestconfig.rootpath)

    assert (
        "PHP_BINARY"
        in host.run_expect(
            [0],
            f"{container_runtime.runner_binary} run --rm {container_image.container_id} -r 'print_r(get_defined_constants());'",
        ).stdout
    )


@pytest.mark.parametrize(
    "container_per_test",
    [MEDIAWIKI_APACHE_CONTAINER],
    indirect=["container_per_test"],
)
def test_mediawiki_php_apache(
    container_per_test: ContainerData,
    host,
) -> None:
    host.run_expect(
        [0],
        f"curl --fail http://localhost:{container_per_test.forwarded_ports[0].host_port}",
    )


@pytest.mark.parametrize(
    "pod_per_test", [MEDIAWIKI_FPM_POD], indirect=["pod_per_test"]
)
def test_mediawiki_fpm_build(
    pod_per_test: PodData,
    host,
):
    host.run_expect(
        [0],
        f"curl --fail http://localhost:{pod_per_test.forwarded_ports[0].host_port}",
    )
