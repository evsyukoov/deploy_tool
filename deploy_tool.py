import os

from fabric import *
import yaml
import xml.etree.ElementTree
import xml.dom.minidom

from maven_item import MavenItem


# Test vpn_server by using ~/.ssh/config
# conf = Config()
# conn1 = Connection(config=conf, host='vpn_server')
# test_basic_command(conn1)

# Test main server by using user/pass

def test_basic_command(conn):
    uname = conn.run('uname -s', hide=False)
    if 'Linux' in uname.stdout:
        command = "pwd"
        return conn.run(command).stdout.strip()


def open_connection(settings):
    conn = Connection(host=settings['host'], user=settings['user'],
                      port=settings['port'], connect_kwargs={"password": settings['password']})
    return conn


def parse_yaml():
    with open('connection_config.yaml') as f:
        file = yaml.safe_load(f)
    return file


def prepare_installation_info(pom, conn):
    with open(pom.name) as f:
        doc = xml.dom.minidom.parse(f)
        modules = list()
        elements = doc.getElementsByTagName("module")
        if elements is None:
            return MavenItem(False)
        else:
            for elem in elements:
                module = elem.firstChild.data
                # если у модуля нет mainClass то запускать его будет не нужно
                command = "cat '{module}/pom.xml'".format(
                    module=module) + " | grep 'mainClass'"  # grep exitCode==1, если ничего нет в stdout!
                res = conn.run(command, warn=True)
                if res.return_code == 0:
                    modules.append(elem.firstChild.data)

        return MavenItem(True, modules)


def kill_running_installations(jar_names, conn):
    for name in jar_names:
        command = "ps aux | grep {name} | grep -v grep | sed 's/   */ /g' | cut -d ' '  -f2 | head -n 1" \
            .format(name=name)
        res = conn.run(command, warn=True)
        if res.return_code == 0 and res.stdout != "":
            command = "kill -9 {process}".format(process=res.stdout)
            conn.run(command)
            print("3. Kill running installation of {name} with pid {pid} ------------------- ✅"
                  .format(name=name, pid=res.stdout))
        elif res.return_code == 1 or res.stdout == "":
            print("3. No running installation of {name} on server".format(name=name))


def start_new_installation(maven_item, conn):
    if maven_item.is_several_modules:
        for it in maven_item.modules:
            with (conn.cd("{module_name}".format(module_name=it))):
                # делаем так поскольку не знаем версию джарника, лучше брать из pom и знать какой джарник будет лежать
                find_jar_command = "ls target | egrep '{module_name}.*.jar$'".format(module_name=it)
                compiled_jar = conn.run(find_jar_command).stdout.strip()
                start_jar = "java -jar target/{jar_name}>/dev/null 2>&1".format(jar_name=compiled_jar)
                conn.run(start_jar)



def deploy(item, conn):
    print("Start build {name} project".format(name=item['name']))
    print("-------------------------------------------------")
    with (conn.cd(item['dir-path'])):
        # git_pull_command = "git pull"
        # res = conn.run(git_pull_command)
        # if not res.failed:
        #     print("1. Git pull project ------------------- ✅")
        # else:
        #     print("1. Git pull project ------------------- 🚫")
        #     print("Cause: {reason}".format(reason=res.stderr))
        #     return False
        #
        # build_command = "mvn clean package"
        # res = conn.run(build_command)
        # if not res.failed:
        #     print("2. Build project ------------------- ✅")
        # else:
        #     print("2. Build project ------------------- 🚫")
        #     print("Cause: {reason}".format(reason=res.stderr))
        #     return False

        cat_command = "cat pom.xml"
        res = conn.run(cat_command).stdout
        tmp_pom = open('pom.xml', 'w+')
        tmp_pom.write(res)
        tmp_pom.close()
        maven_item = prepare_installation_info(tmp_pom, conn)
        os.remove(tmp_pom.name)
        #kill_running_installations(maven_item.modules, conn)
        #print("3. Kill running installations ------------------- ✅")
        start_new_installation(maven_item, conn)
        print("4. Start new installations ------------------- ✅")


if __name__ == '__main__':
    templates = parse_yaml()
    ssh_connection_settings = templates['ssh-connection']
    connection = open_connection(ssh_connection_settings)
    test_basic_command(connection)
    deploy_items = list(filter(lambda it: (it['need-deploy']), templates['deploy-items']))

    for item in deploy_items:
        deploy(deploy_items[0], connection)
