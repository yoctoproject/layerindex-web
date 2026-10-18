# layerindex-web - tests for the file editing done by dockersetup.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import os
import shutil
import stat

import pytest
import yaml

# The Docker image doesn't contain dockersetup.py or the files it edits, so
# these tests are skipped by docker/run-tests.sh; CI runs them on the host.
dockersetup = pytest.importorskip('dockersetup')

basepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

TRACKED_FILES = [
    'docker-compose.yml',
    '.env.dev.app', '.env.dev.celery', '.env.dev.db', '.env.dev.rabbit',
    'Dockerfile',
    'docker/git-proxy', 'docker/.gitconfig', 'docker/nginx-ssl.conf',
]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """A copy of the files dockersetup.py edits, as the current directory."""
    for name in TRACKED_FILES:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(basepath, name), dest)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            values[key] = value
    return values


def write_env_files(email_host=None, email_tls=False):
    dockersetup.write_service_env_files('dbpw', 'rootpw', 'sekrit', 'mqpw', email_host, None,
                                        None, None, False, email_tls)


def test_env_files_get_generated_secrets(workdir):
    write_env_files(email_host='smtp.example.com', email_tls=True)

    app = read_env(workdir / '.env.local.app')
    assert app['SECRET_KEY'] == 'sekrit'
    assert app['DATABASE_USER'] == 'layers'
    assert app['DATABASE_PASSWORD'] == 'dbpw'
    assert app['RABBITMQ_DEFAULT_USER'] == 'layermq'
    assert app['RABBITMQ_DEFAULT_PASS'] == 'mqpw'
    assert app['EMAIL_HOST'] == 'smtp.example.com'
    assert app['EMAIL_USE_TLS'] == 'True'
    assert app['DEBUG'] == '0'
    assert read_env(workdir / '.env.local.celery')['DATABASE_PASSWORD'] == 'dbpw'
    assert read_env(workdir / '.env.local.db')['MYSQL_ROOT_PASSWORD'] == 'rootpw'
    assert read_env(workdir / '.env.local.rabbit') == {'RABBITMQ_DEFAULT_USER': 'layermq',
                                                       'RABBITMQ_DEFAULT_PASS': 'mqpw'}


def test_env_files_are_private_and_leave_unset_email_commented(workdir):
    write_env_files()
    for service in ('app', 'celery', 'db', 'rabbit'):
        path = workdir / ('.env.local.' + service)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert 'not secret' not in path.read_text()
    app = read_env(workdir / '.env.local.app')
    assert 'EMAIL_HOST' not in app
    assert 'EMAIL_USE_TLS' not in app
    # The tracked defaults are left alone
    assert read_env(workdir / '.env.dev.db')['MYSQL_ROOT_PASSWORD'] == 'testingpw'


def load_compose(workdir):
    return yaml.safe_load((workdir / 'docker-compose.yml').read_text())


def test_compose_uses_local_env_files(workdir):
    dockersetup.edit_dockercompose('layers.example.com', '8080:80,8081:443', False)
    services = load_compose(workdir)['services']
    for service, env in (('layersdb', 'db'), ('layersapp', 'app'),
                         ('layersrabbit', 'rabbit'), ('layerscelery', 'celery')):
        assert services[service]['env_file'] == ['.env.local.' + env]
    assert services['layersapp']['hostname'] == 'layers.example.com'
    assert services['layersweb']['ports'] == ['8080:80', '8081:443']
    assert 'layerscertbot' not in services


def test_compose_enables_certbot_for_letsencrypt(workdir):
    dockersetup.edit_dockercompose('layers.example.com', '80:80,443:443', True)
    services = load_compose(workdir)['services']
    assert 'layerscertbot' in services
    assert './docker/certs:/etc/letsencrypt' in services['layerscertbot']['volumes']
    assert './docker/certs:/etc/letsencrypt' in services['layersweb']['volumes']


def test_read_db_root_password(workdir):
    assert dockersetup.read_db_root_password() == 'testingpw'
    # Installations made before .env.local.db kept it in docker-compose.yml
    compose = workdir / 'docker-compose.yml'
    compose.write_text(compose.read_text() + '    environment:\n     - "MYSQL_ROOT_PASSWORD=oldpw"\n')
    assert dockersetup.read_db_root_password() == 'oldpw'
    write_env_files()
    assert dockersetup.read_db_root_password() == 'rootpw'


def test_dockerfile_proxy(workdir):
    dockersetup.edit_dockerfile('http://proxy:3128', 'http://proxy:3128', 'localhost')
    text = (workdir / 'Dockerfile').read_text()
    assert 'ENV http_proxy http://proxy:3128\n' in text
    assert 'ENV no_proxy localhost\n' in text
    dockersetup.edit_dockerfile('', '', '')
    lines = (workdir / 'Dockerfile').read_text().splitlines()
    assert not [line for line in lines if line.startswith(('ENV http_proxy', 'ENV https_proxy', 'ENV no_proxy'))]


@pytest.mark.parametrize('no_proxy, expected', [
    ('localhost,.example.com', 'localhost|*.example.com'),
    ('10.0.0.0/8,192.168.1.0/24,10.1.2.3/32', '10.*|192.168.1.*|10.1.2.3'),
    ('172.16.0.0/12', ''),
])
def test_convert_no_proxy(no_proxy, expected):
    assert dockersetup.convert_no_proxy(no_proxy) == expected


def test_gitproxy(workdir):
    dockersetup.edit_gitproxy('socks.example.com', '1080', 'localhost,.example.com')
    proxy = (workdir / 'docker' / 'git-proxy').read_text()
    assert 'PROXY=socks.example.com\n' in proxy
    assert 'PORT=1080\n' in proxy
    assert '    localhost|*.example.com)\n' in proxy
    gitconfig = (workdir / 'docker' / '.gitconfig').read_text()
    assert any('gitproxy' in line and not line.lstrip().startswith('#') for line in gitconfig.splitlines())

    dockersetup.edit_gitproxy('', '', '')
    gitconfig = (workdir / 'docker' / '.gitconfig').read_text()
    assert all(line.lstrip().startswith('#') for line in gitconfig.splitlines() if 'gitproxy' in line)


def test_nginx_ssl_conf_round_trip(workdir):
    dockersetup.edit_nginx_ssl_conf('layers.example.com', '8081', '/opt/cert', 'cert.pem', 'key.pem')
    edited = (workdir / 'docker' / 'nginx-ssl-edited.conf').read_text()
    assert 'ssl_dhparam /opt/cert/dhparam.pem;' in edited
    assert 'layers.openembedded.org' not in edited
    # The template is left alone, so the hostname can be replaced again
    assert 'layers.openembedded.org' in (workdir / 'docker' / 'nginx-ssl.conf').read_text()
    assert dockersetup.read_nginx_ssl_conf('/opt/cert') == \
        ('layers.example.com', '8081', '/opt/cert', 'cert.pem', 'key.pem')


@pytest.mark.parametrize('result, expected', [
    (0, ['docker', 'compose', 'up']),
    (1, ['docker-compose', 'up']),
    (FileNotFoundError(), ['docker-compose', 'up']),
])
def test_compose_command(monkeypatch, result, expected):
    calls = []

    def fake_call(cmd, **kwargs):
        calls.append(cmd)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(dockersetup.subprocess, 'call', fake_call)
    dockersetup.compose_command.cache_clear()
    try:
        assert dockersetup.compose('up') == expected
        assert dockersetup.compose_sh() == ' '.join(expected[:-1])
        # Detected once and then reused
        assert calls == [['docker', 'compose', 'version']]
    finally:
        dockersetup.compose_command.cache_clear()
