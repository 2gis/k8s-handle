# k8s-handle

Easy CI/CD for Kubernetes clusters with python and jinja2

k8s-handle is a command line tool that facilitates continuous delivery for Kubernetes applications.
Also k8s-handle supports environments, so you can use same deployment templates for different environments like `staging` and `production`.
k8s-handle is a helm alternative, but without package manager

# Table of contents
* [Features](#features)
* [k8s-handle vs helm](#k8s-handle-vs-helm)
* [Before you begin](#before-you-begin)
* [Installation with pip](#installation-with-pip)
* [Usage with docker](#usage-with-docker)
* [Usage with CI/CD tools](#usage-with-cicd-tools)
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
     * [Sync mode](#sync-mode)
     * [Strict mode](#strict-mode)
  * [Destroy](#destroy)
  * [Operating without config.yaml](#operating-without-configyaml)
     * [Render](#render)
     * [Apply](#apply)
     * [Delete](#delete)
  
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
# Installation with pip
Required python 3.4 or higher
```
$ pip install k8s-handle
 -- or --
$ pip install --user k8s-handle
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

# Usage with CI/CD tools
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
$ k8s-handle deploy -s staging --use-kubeconfig
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
$ k8s-handle deploy -s staging --use-kubeconfig --sync-mode
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
$ k8s-handle deploy -s staging --use-kubeconfig --sync-mode
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
k8s-handle works with 2 components:
 * config.yaml (or any other yaml file through -c argument) that stores all configuration for deploy
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
Templates in k8s-handle use jinja2 syntax and support all standard filters + some special
### Filters
* `{{ my_var | b64encode }}` - encode value of my_var to base64
* `{{ my_var | b64decode }}` - decode value of my_var from base64
* `{{ my_var | hash_sha256 }}` - encode value of my_var to sha256sum
> Warning: You can use filters only for templates and can't for config.yaml
### Functions
* `{{ include_file('my_file.txt') }}` - include my_file.txt to resulting resource w/o parsing it, useful for include configs to configmap.
my_file.txt will be searched in parent directory of templates dir(most of the time - k8s-handle project dir):
```bash
$ ls -1
config.yaml
templates
my_file.txt
...
``` 
> Note, `include_file` also support unix glob. You can import all files from directory conf.d/*.conf for example.

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
### Template loader path 
k8s-handle uses jinja2 template engine and initializes it with base folder specified in the TEMPLATES_DIR env variable.
Jinja environment considers template paths as specified relatively to its base init directory. 

Therefore, users **must** specify paths in `{% include %}` (and other) blocks relatively to the base (TEMPLATES_DIR) folder, not relative to the importer template location.

Example

We have the following templates dir content layout:
```
templates /
     subdirectory /
         template_A.yaml
         template_B.yaml
```
In that scheme, if template_A contains jinja2 import of the template_B, that import statement must be
```
{% include "subdirectory/template_B.yaml" %}
```
despite that included template lies as the same level as the template where include is used.

### Tags
If you have a large deployment with many separate parts (for ex. main application and migration job), you can want to deploy them independently. In this case you have two options:
* Use multiple isolated sections (like `production_app`, `production_migration`, etc.)
* Use one section and tag yours templates. For example:
    ```yaml
    production:
      templates:
      - template: my-job.yaml.j2
        tags: migration
      - template: my-configmap.yaml.j2
        tags: ['app', 'config']
      - template: my-deployment.yaml.j2
        tags:
        - app
        - deployment
      - template: my-service.yaml.j2
        tags: "app,service"
    ```
Since you templates are tagged you can use `--tags`/`--skip-tags` keys to partial deploy. For example, you can delete only a migration job:
```
k8s-handle destroy --section production --tags migration
```
Command line keys `--tags` and `--skip-tags` can be specified multiple times, for ex.:
```
k8s-handle deploy --section production --tags=tag1 --tags=tag2 --tags=tag3
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
All variables defined in `common` will be merged with deployed section and available as context dict in templates rendering,
for example: 
```yaml
common:
  common_var: common_value 
testing:
  testing_variable: testing_value
```
After the rendering of this template some-file.txt.j2:
```txt
common_var = {{ common_var }}
testing_variable = {{ testing_variable }}
```
file some-file.txt will be generated with the following content:
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
### Destroy
In some cases you need to destroy early created resources(demo env, deploy from git branches, testing etc.), k8s-handle
support `destroy` subcommand for you. Just use `destroy` instead of `deploy`. k8s-handle process destroy as deploy, but
call delete kubernetes api calls instead of create or replace. 
> Sync mode is available for destroy as well.

## Operating without config.yaml
The most common way for the most of use cases is to operate with k8s-handle via `config.yaml`, specifying
connection parameters, targets (sections and tags) and variables in one file. The deploy command that runs after that, 
at first will trigger templating process: filling your spec templates with variables, creating resource spec files.
That files become a targets for the provisioner module, which does attempts to create K8S resources.

But in some cases, such as the intention to use your own templating engine or, probably, necessity to make specs 
beforehand and to deploy them separately and later, there may be a need to divide the process into the separate steps:
1. Templating
2. Direct, `kubectl apply`-like provisioning without config.yaml context.

For this reason, `k8s-handle render`, `k8s-handle apply`, `k8s-handle delete` commands are implemented.

### Render

`render` command is purposed for creating specs from templates without their subsequent deployment. 

Another purpose is to check the generation of the templates: previously, this functionality was achieved by using the
`--dry-run` optional flag. The support of `--dry-run` in `deploy` and `destroy` commands remains at this time for the
sake of backward compatibility but it's **discouraged** for the further usage.

Just like with `deploy` command, `-s/--section` and `--tags`/`--skip-tags` targeting options are provided to make it
handy to render several specs. Connection parameters are not needed to be specified cause no k8s cluster availability
checks are performed.

Templates directory path is taken from env `TEMPLATES_DIR` and equal to 'templates' by default.
Resources generated by this command can be obtained in directory that set in `TEMP_DIR` env variable
with default value '/tmp/k8s-handle'. Users that want to preserve generated templates might need to change this default 
to avoid loss of the generated resources.

```
TEMP_DIR="/home/custom_dir" k8s-handle render -s staging
2019-02-15 14:44:44 INFO:k8s_handle.templating:Trying to generate file from template "service.yaml.j2" in "/home/custom_dir"
2019-02-15 14:44:44 INFO:k8s_handle.templating:File "/home/custom_dir/service.yaml" successfully generated
```

### Apply

`apply` command with the `-r/--resource` required flag starts the process of provisioning of separate resource 
spec to k8s.

The value of `-r` key is considered as absolute path if it's started with slash. Otherwise, it's considered as
relative path from directory specified in `TEMP_DIR` env variable.

No config.yaml-like file is required (and not taken into account even if exists). The connection parameters can be set
via `--use-kubeconfig` mode which is available and the most handy, or via the CLI/env flags and variables.
Options related to output and syncing, like `--sync-mode`, `--tries` and `--show-logs` are available as well.

```
$ k8s-handle apply -r /tmp/k8s-handle/service.yaml --use-kubeconfig
2019-02-15 14:22:58 INFO:k8s_handle:Default namespace "test"
2019-02-15 14:22:58 INFO:k8s_handle.k8s.resource:Using namespace "test"
2019-02-15 14:22:58 INFO:k8s_handle.k8s.resource:Service "k8s-handle-example" does not exist, create it

```

### Delete
`delete` command with the `-r/--resource` required flag acts similarly to `destroy` command and does a try to delete
 the directly specified resource from k8s if any.

```
$ k8s-handle delete -r service.yaml --use-kubeconfig

2019-02-15 14:24:06 INFO:k8s_handle:Default namespace "test"
2019-02-15 14:24:06 INFO:k8s_handle.k8s.resource:Using namespace "test"
2019-02-15 14:24:06 INFO:k8s_handle.k8s.resource:Trying to delete Service "k8s-handle-example"
2019-02-15 14:24:06 INFO:k8s_handle.k8s.resource:Service "k8s-handle-example" deleted
```

### Custom resource definitions and custom resources
Since version 0.5.5 k8s-handle supports Custom resource definition (CRD) and custom resource (CR) kinds.
If your deployment involves use of such kinds, make sure that CRD was deployed before CR and check correctness of the CRD's scope.
