# k8s-handle

Easy CI/CD for Kubernetes clusters with python and jinja2

k8s-handle is a command line tool that facilitates continuous delivery for Kubernetes applications.
Also k8s-handle supports environments, so you can use same deployment templates for different environments like `staging` and `production`.
k8s-handle is a helm alternative, but without package manager

# Table of contents
* [Features](#features)
* [k8s-handle vs helm](#k8s-handle-vs-helm)
* [Before you begin](#before-you-begin)
* [Usage with docker](#usage-with-docker)
* [Using with CI/CD tools](#using-with-cicd-tools)
* [Usage](#usage)
* [Example](#example)
* [Docs](#docs)
  * [Configuration structure](#configuration-structure)
  * [Environments](#environments)
     * [Common section](#common-section)
     * [Any other sections](#any-other-sections)
     * [Deploy specific environment](#deploy-specific-environment)
  * [Templates](#templates)
  * [Variables](#variables)
     * [Merging with common](#merging-with-common)
     * [Load variables from environment](#load-variables-from-environment)
     * [Load variables from yaml file](#load-variables-from-yaml-file)
  * [How to use in CI/CD](#how-to-use-in-cicd)
     * [Gitlab CI](#gitlab-ci)
        * [Native integration](#native-integration)
        * [Through variables](#through-variables)
  * [Working modes](#working-modes)
     * [Dry run](#dry-run)
     * [Sync mode](#sync-mode)
     * [Strict mode](#strict-mode)
  * [Destroy](#destroy)
  
# Features
* Easy to use command line interface
* Configure any variables in one configuration file (config.yaml)
* Templating for kubernetes resource files (jinja2) with includes, loops, if-else and so on. 
* Loading variables from environment
* Includes for configuration (includes in config.yaml) for big deploys
* Async and sync mode for deploy (wait for deployment, statefulset, daemonset ready)
* Strict mode, stop deploy if any warning appear
* Easy integration with CI pipeline (gitlab ci for example)
* Ability to destroy resources (deploy and destroy from git branches, gitlab environments)

# k8s-handle vs helm
* k8s-handle acts like template parser and provisioning tool, but not package manager included like in helm
* k8s-handle don't need in cluster tools like The Tiller Server, you need only ServiceAccount for deploy
* k8s-handle secure by default, you don't need to generate any certificates for deploying application, k8s-handle uses kubernetes REST API with https, like kubectl

![Deploy process](/helmVsK8s-handle.png)

# Before you begin
* Setup Kubernetes cluster [https://kubernetes.io/docs/setup/](https://kubernetes.io/docs/setup/), or use any predefined
* Install `kubectl` if you don't have it [https://kubernetes.io/docs/tasks/tools/install-kubectl/](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
* Create kubeconfig(~/.kube/config) or skip if you already have one
```bash
$ cat > ~/.kube/kubernetes.ca.crt << EOF
> <paste your cluster CA here>
>EOF
cat > ~/.kube/config << EOF
apiVersion: v1
kind: Config
preferences: {}
clusters:
- cluster:
    certificate-authority: kubernetes.ca.crt
    server: < protocol://masterurl:port >
  name: my-cluster
contexts:
- context:
    cluster: my-cluster
    namespace: my-namespace
    user: my-user
  name: my-context
current-context: my-context
users:
- name: my-user
  user:
    token: <your token>
EOF
```

# Usage with docker
```bash
$ cd $WORKDIR
$ git clone https://github.com/2gis/k8s-handle-example.git
$ cd k8s-handle-example
$ docker run --rm -v $(pwd):/tmp/ -v "$HOME/.kube:/root/.kube" 2gis/k8s-handle k8s-handle deploy -s staging --use-kubeconfig
INFO:templating:File "/tmp/k8s-handle/configmap.yaml" successfully generated
INFO:templating:Trying to generate file from template "secret.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/secret.yaml" successfully generated
INFO:templating:Trying to generate file from template "deployment.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/deployment.yaml" successfully generated
INFO:k8s.resource:ConfigMap "k8s-starter-kit-nginx-conf" already exists, replace it
INFO:k8s.resource:Secret "k8s-starter-kit-secret" already exists, replace it
INFO:k8s.resource:Deployment "k8s-starter-kit" does not exist, create it

                         _(_)_                          wWWWw   _
             @@@@       (_)@(_)   vVVVv     _     @@@@  (___) _(_)_
            @@()@@ wWWWw  (_)\    (___)   _(_)_  @@()@@   Y  (_)@(_)
             @@@@  (___)     `|/    Y    (_)@(_)  @@@@   \|/   (_)
              /      Y       \|    \|/    /(_)    \|      |/      |
           \ |     \ |/       | / \ | /  \|/       |/    \|      \|/
            \|//    \|///    \|//  \|/// \|///    \|//    |//    \|//
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

# Using with CI/CD tools
If you using Gitlab CI, TeamCity or something else, you can use docker runner/agent, script will slightly different: 
```bash
$ k8s-handle deploy -s staging
```
Configure checkout for https://github.com/2gis/k8s-handle-example.git and specific branch `without-kubeconfig`
Also you need to setup next env vars:
* K8S_NAMESPACE
* K8S_MASTER_URI
* K8S_CA_BASE64
* K8S_TOKEN

use image 2gis/k8s-handle:<version or latest>

Notice: If you use Gitlab CI, you can configure [Kubernetes integration](https://docs.gitlab.com/ee/user/project/clusters/#adding-an-existing-kubernetes-cluster) and just use `--use-kubeconfig` flag.

# Usage
```bash
$ python k8s-handle.py deploy -s staging --use-kubeconfig
INFO:templating:Trying to generate file from template "configmap.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/configmap.yaml" successfully generated
INFO:templating:Trying to generate file from template "secret.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/secret.yaml" successfully generated
INFO:templating:Trying to generate file from template "deployment.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/deployment.yaml" successfully generated
INFO:k8s.resource:ConfigMap "k8s-starter-kit-nginx-conf" already exists, replace it
INFO:k8s.resource:Secret "k8s-starter-kit-secret" already exists, replace it
INFO:k8s.resource:Deployment "k8s-starter-kit" does not exist, create it

                         _(_)_                          wWWWw   _
             @@@@       (_)@(_)   vVVVv     _     @@@@  (___) _(_)_
            @@()@@ wWWWw  (_)\    (___)   _(_)_  @@()@@   Y  (_)@(_)
             @@@@  (___)     `|/    Y    (_)@(_)  @@@@   \|/   (_)
              /      Y       \|    \|/    /(_)    \|      |/      |
           \ |     \ |/       | / \ | /  \|/       |/    \|      \|/
            \|//    \|///    \|//  \|/// \|///    \|//    |//    \|//
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
$ kubectl get configmap 
NAME                         DATA      AGE
k8s-starter-kit-nginx-conf   1         1m
$ kubectl get secret | grep starter-kit
k8s-starter-kit-secret   Opaque                                1         1m
$ kubectl get deploy
NAME              DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
k8s-starter-kit   1         1         1            1           3m
```
Now set replicas_count in config.yaml to 3, and run again in sync mode 
```bash
$ python k8s-handle.py deploy -s staging --use-kubeconfig --sync-mode
...
INFO:k8s.resource:Deployment "k8s-starter-kit" already exists, replace it
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 1
INFO:k8s.resource:Deployment not completed on 1 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 2
INFO:k8s.resource:Deployment not completed on 2 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 3
INFO:k8s.resource:Deployment completed on 3 attempt
...
$ kubectl get deploy
NAME              DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
k8s-starter-kit   3         3         3            3           7m
```

# Example
You can start by example https://github.com/2gis/k8s-handle-example. There are nginx with index.html and all needed kubernetes resources for deploy them.
```bash
$ cd $WORKDIR
$ git clone https://github.com/2gis/k8s-handle-example.git
$ cd k8s-handle-example
$ IMAGE_VERSION=latest k8s-handle-os deploy -s staging --use-kubeconfig --sync-mode
INFO:__main__:Using default namespace k8s-handle-test
INFO:templating:Trying to generate file from template "configmap.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/configmap.yaml" successfully generated
INFO:templating:Trying to generate file from template "deployment.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/deployment.yaml" successfully generated
INFO:templating:Trying to generate file from template "service.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/service.yaml" successfully generated
INFO:k8s.resource:ConfigMap "example-nginx-conf" does not exist, create it
INFO:k8s.resource:Deployment "example" does not exist, create it
INFO:k8s.resource:desiredReplicas = 1, updatedReplicas = 1, availableReplicas = None
INFO:k8s.resource:Deployment not completed on 1 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 1, updatedReplicas = 1, availableReplicas = None
INFO:k8s.resource:Deployment not completed on 2 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 1, updatedReplicas = 1, availableReplicas = 1
INFO:k8s.resource:Deployment completed on 3 attempt
INFO:k8s.resource:Service "example" does not exist, create it
$ kubectl -n k8s-handle-test get svc 
NAME      TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
example   NodePort   10.100.132.168   <none>        80:31153/TCP   52s
$ curl http://<any node>:31153
<h1>Hello world!</h1>
Deployed with k8s-handle.
```

# Docs
## Configuration structure
k8s-handle work with 2 components:
 * conifg.yaml (or any other yaml file through -c argument) store all configuration for deploy
 * templates catalog, where your can store all required templates for kubernetes resource files (can be changed through
 TEMPLATES_DIR env var)

## Environments
If your have testing, staging, production-zone-1, production-zone-2, etc, you can easily cover all environments with
one set of templates for your application without duplication.
### Common section
In the common section you can specify variables that you want to combine with the variables of the selected section:
```yaml
common:
    app_name: my-shiny-app
    app_port: 8080
```
Both of these example variables will be added to variables of the selected section.
Common section is optional and can be omitted.
### Any other sections
Let's specify testing environment
```yaml
testing:
    replicas: 1
    request_cpu: 100m 
    request_memory: 128M
    some_option: disabled
```
In testing in most cases we don't want performance from our application so we can keep 1 replica and small
amount of resources for it. Also you can set some options to disabled state, in case when you don't want to affect
any integrated systems during testing during testing.
```yaml
staging:
    replicas: 2
    request_cpu: 200m 
    request_memory: 512M
```
Some teams use staging for integration and demo, so we can increase replicas and resources for our service.
```yaml
production-zone-1:
    replicas: 50
    request_cpu: 1000m
    request_memory: 1G
    production: "true"
    never_give_up: "true"
```
In production we need to process n thousand RPS, so set replicas to 50, increase resources and set all production
variables to ready for anything values.
### Deploy specific environment
In your CI/CD script you can deploy any environment
```bash
$ k8s-handle deploy -s staging # Or testing or production-zone-1
```
In Gitlab CI for example you can create manual job for each environment

## Templates 
Templates in k8s-handle use jinja2 syntax and support all standard filters + some special:
* {{ my_var | b64encode }} - encode value of my_var to base64
* {{ my_var | b64decode }} - decode value of my_var from base64
* {{ my_var | hash_sha256 }} - encode value of my_var to sha256sum
Also global function
* {{ include_file('my_file.txt') }} - include my_file.txt to resulting resource w/o parsing it, useful for include configs to configmap.
my_file.txt will be searched in parent directory of templates dir(most of the time - k8s-handle project dir):
```bash
$ ls -1
config.yaml
templates
my_file.txt
...
``` 
> Warning: You can use filters only for templates and can't for config.yaml

You can put *.j2 templates in 'templates' directory and specify it in config.yaml
```yaml
testing:
    replicas: 1
    request_cpu: 100m 
    request_memory: 128M
    some_option: disabled
    templates:
    - template: my-deployment.yaml.j2
```
the same template you can use in each section you want:
```yaml
staging:
    ...
    templates:
    - template: my-deployment.yaml.j2
    
production-zone-1:
  ...
  templates:
  - template: my-deployment.yaml.j2
```
## Variables
### Required parameters
k8s-handle needs several parameters to be set in order to connect to k8s, such as:
* K8S master uri
* K8S CA base64
* K8S token

Each of these parameters can be set in various ways in any combination and are applied with the following order 
(from highest to lowest precedence):
1. From the command line via corresponding keys
2. From the config.yaml section, lowercase, underscore-delimited, e.g. `k8s_master_uri`
3. From environment, uppercase, underscore-delimited, e.g `K8S_MASTER_URI`

If the --use-kubeconfig flag is used, these explicitly specified parameters are ignored.

In addition, the `K8S namespace` parameter also must be specified.
k8s-handle uses namespace specified in `metadata: namespace` block of a resource.
If it is not present, the default namespace is used, which is evaluated in the following 
order (from highest to lowest precedence):
1. From the config.yaml `k8s_namespace` key
2. From the kubeconfig `current-context` field, if --use-kubeconfig flag is used
3. From the environment `K8S_NAMESPACE` variable

If the namespace is not specified in the resource spec, and the default namespace is also not specified, 
this will lead to a provisioning error.

The one of the common ways is to specify connection parameters and/or k8s_namespace in the `common` section of your 
config.yaml, but you can do it in another way if necessary.

Thus, the k8s-handle provides flexible ways to set the required parameters. 

### Merging with common
All variables defined in common merged with deployed section and available as context dict in templates rendering,
for example: 
```yaml
common:
  common_var: common_value 
testing:
  testing_variable: testing_value
```
After rendering this template some-file.txt.j2:
```txt
common_var = {{ common_var }}
testing_variable = {{ testing_variable }}
```
will be generated file some-file.txt with content:
```txt
common_var = common_value
testing_variable = testing_value
```

If the variable is declared both in `common` section and the selected one, the value from the 
selected section will be chosen.

If the particular variable is a dictionary in both (`common` and the selected one) sections, resulting variable
will contain merge of these two dictionaries.

### Load variables from environment
If you want to use environment variables in your templates(for docker image tag generated by build for example),
you can use next construction in config.yaml:
```yaml
common:
  image_version: "{{ env='TAG' }}"
```
### Load variables from yaml file
```yaml
common:
  test: "{{ file='include.yaml' }}"
```
include.yaml:
```yaml
- 1
- 2 
- 3
```
template:
```text
{{ test[0] }}
{{ test[1] }}
{{ test[2] }}
```
After rendering you get:
```text
1
2
3
```
## How to use in CI/CD
### Gitlab CI
#### Native integration
Use Gitlab CI integration with Kubernetes (https://docs.gitlab.com/ee/user/project/clusters/index.html#adding-an-existing-kubernetes-cluster)
.gitlab-ci.yaml:
```yaml
deploy:
  image: 2gis/k8s-handle:latest
  script:
    - k8s-handle deploy --section <section_name> --use-kubeconfig
```
#### Through variables
Alternatively you can setup Gitlab CI variables:
* K8S_TOKEN_STAGING = < serviceaccount token for staging >
* K8S_TOKEN_PRODUCTION = < serviceaccount token for production >
> Don't forget mark variables as protected

then add next lines to config.yaml
```yaml
staging:
  k8s_master_uri: <kubenetes staging master uri>
  k8s_token: "{{ env='K8S_TOKEN_STAGING' }}"
  k8s_ca_base64: <kubernetes staging ca>
  
production:
  k8s_master_uri: <kubenetes production master uri>
  k8s_token: "{{ env='K8S_TOKEN_PRODUCTION' }}"
  k8s_ca_base64: <kubernetes production ca>
```
Now just run proper gitlab job(without --use-kubeconfig option):
```yaml
deploy:
  image: 2gis/k8s-handle:latest
  script:
    - k8s-handle deploy --section <section_name>
```
## Working modes
### Dry run
If you want check templates generation and not apply changes to kubernetes use --dry-run function.
```bash
$ k8s-handle deploy -s staging --use-kubeconfig --dry-run
INFO:templating:Trying to generate file from template "configmap.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/configmap.yaml" successfully generated
INFO:templating:Trying to generate file from template "deployment.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/deployment.yaml" successfully generated
INFO:templating:Trying to generate file from template "service.yaml.j2" in "/tmp/k8s-handle"
INFO:templating:File "/tmp/k8s-handle/service.yaml" successfully generated
$ cat /tmp/k8s-handle/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: example
spec:
  type: NodePort
  ports:
    - name: http
      port: 80
      targetPort: 80
  selector:
    app: example 
```
### Sync mode
> Works only with Deployment, Job, StatefulSet and DaemonSet

By default k8s-handle just apply resources to kubernetes and exit. In sync mode k8s-handle wait for resources up and
running
```bash
$ k8s-handle deploy --section staging  --sync-mode
...
INFO:k8s.resource:Deployment "k8s-starter-kit" already exists, replace it
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 1
INFO:k8s.resource:Deployment not completed on 1 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 2
INFO:k8s.resource:Deployment not completed on 2 attempt, next attempt in 5 sec.
INFO:k8s.resource:desiredReplicas = 3, updatedReplicas = 3, availableReplicas = 3
INFO:k8s.resource:Deployment completed on 3 attempt
...
```
You can specify number of tries before k8s-handle exit with non zero exit code and delay before checks:
```bash
--tries <tries> (360 by default)
--retry-delay <retry-delay in seconds> (5 by default)
```
### Strict mode
In some cases k8s-handle warn you about ambiguous situations and keep working. With `--strict` mode k8s-handle warn and exit 
with non zero code. For example when some used environment variables is empty.
```bash
$ k8s-handle-os deploy -s staging --use-kubeconfig --strict
ERROR:__main__:RuntimeError: Environment variable "IMAGE_VERSION" is not set
$ echo $?
1
```
## Destroy
In some cases you need to destroy early created resources(demo env, deploy from git branches, testing etc.), k8s-handle
support `destroy` subcommand for you. Just use `destroy` instead of `deploy`. k8s-handle process destroy as deploy, but
call delete kubernetes api calls instead of create or replace. 
> Sync mode available for destroy too
