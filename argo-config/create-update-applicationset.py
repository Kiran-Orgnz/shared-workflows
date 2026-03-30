import yaml
import sys
import os
from pathlib import Path
import shutil

def re_create_folder(repo_name):
    os.makedirs(repo_name)
    chart_path = repo_name+'/Chart.yaml'
    with open(chart_path, 'w') as file: 
        file.write('apiVersion: v2\nname: Infra-ApplicationSet\nversion: 0.1.0\nappVersion: "1.0.0"') 

'''
 * Build ArgoCD teams annotations from the provided configuration.
 *
 * @param teams_config - The teams configuration, either a string or a dictionary.
 * @returns A string containing the formatted annotations.
    * If teams_config is a string, it will create annotations for the events: on-sync-succeeded, on-sync-failed, and app-health-degraded.
    * If teams_config is a dictionary, it will use the specified channels and events to create the annotations.
'''
def build_teams_annotations(teams_config):
    if not teams_config:
        return ""

    default_events = [
            "on-sync-succeeded",
            "on-sync-failed",
            "app-health-degraded"
        ]
    
    if isinstance(teams_config, str):
        channels = [teams_config]
        events = default_events

    elif isinstance(teams_config, dict):
        channels = teams_config.get("channels") or [teams_config.get("channel")]
        events = teams_config.get("events", default_events)

    else:
        return ""
    
    # Remove empty values and duplicates while preserving order
    channels = list(dict.fromkeys([c for c in channels if c]))
    events = list(dict.fromkeys([e for e in events if e]))

    lines = ["annotations:"]
    for event in events:
        lines.append(
            f"        notifications.argoproj.io/subscribe.{event}.teams: {';'.join(channels)}"
        )

    return "\n".join(lines)

def create_yaml(application_name, application_project, git_url, env, root_manifest_path, eks_cluster_name, use_branches, append_project, teams_config):
    f = open('argo-config/argo-applicationset-template.yaml','r', encoding="utf8")
    data = f.read()
    f.close()
    
    data = data.replace('{{ArgoApplicationSetName}}', env.lower()+'-'+application_name.lower())
    if use_branches:
       argo_application_name = '{{.path.basenameNormalized}}'
    else:
       argo_application_name = '{{.path.basenameNormalized}}-{{index .path.segments 0}}'
    if append_project:
       argo_application_name = argo_application_name+'-{{ArgoProject}}'
    annotations = build_teams_annotations(teams_config)
    if annotations:
       data = data.replace('{{teams-notification}}', annotations)
    else:
       data = data.replace('\n      {{teams-notification}}', '')
    data = data.replace('{{GitUrl}}', git_url)
    data = data.replace('{{EKSClusterName}}', eks_cluster_name)
    # add if for infra repos so namespace is default
    if use_branches:
        data = data.replace('{{ArgoApplicationName}}', env.lower()+'-'+argo_application_name)
        data = data.replace('{{ApplicationNamespace}}', '{{.path.basenameNormalized}}')
        data = data.replace('{{syncPolicy}}', 'syncPolicy:\n    applicationsSync: create-update\n    preserveResourcesOnDeletion: true')
        data = data.replace('      {{Application-syncPolicy}}\n', '')
        data = data.replace('{{ArgoRootManifestPath}}/', '*')
        data = data.replace('{{Env}}', '')
        data = data.replace('{{GitBranch}}', env.lower())        
    else:
        data = data.replace('{{ArgoRootManifestPath}}', root_manifest_path)
        data = data.replace('{{ArgoApplicationName}}', argo_application_name)
        data = data.replace('{{ApplicationNamespace}}', '{{.path.basenameNormalized}}-{{index .path.segments 0}}-'+application_name.lower())
        data = data.replace('{{GitBranch}}', 'main')
        data = data.replace('{{syncPolicy}}', 'syncPolicy:\n    applicationsSync: create-update\n    preserveResourcesOnDeletion: true')
        data = data.replace('{{Application-syncPolicy}}', 'syncPolicy:\n        automated:\n          prune: true\n          selfHeal: true')
    data = data.replace('{{Env}}', env.lower())
    data = data.replace('{{ArgoProject}}', application_project)
    data = data.replace('{{ValuesFile}}', 'values.yaml')
    return data

try:
    
    for folder in os.listdir("./"):
        if folder != 'argo-config' and folder != '.github' and folder != '.git' and folder != 'README.md':
            shutil.rmtree(folder, ignore_errors=True)
    with open('argo-config/applicationset-config.yaml') as yaml_file:
        inputs = yaml.safe_load(yaml_file)
        for item in inputs:
            if 'repo-url' in item.keys() and 'argo-project-name' in item.keys() and 'argo-application-name' in item.keys() and 'environment-mapping' in item.keys() :
                repo_name = os.path.splitext(os.path.basename(item['repo-url']))[0]
                re_create_folder(repo_name)
                argo_root_manifest_path = '**' if 'argo-root-manifest-path' not in item.keys() else item['argo-root-manifest-path']+'*'
                use_branches = False if 'use-branches' not in item.keys() else item['use-branches']
                append_project = True if 'append-project' not in item.keys() else item['append-project']
                teams_config = item.get('teams-notification', None)
                for mapping in item['environment-mapping']:
                    env = list(mapping.keys())[0]
                    yaml = create_yaml(item['argo-application-name'], item['argo-project-name'], item['repo-url'], env, argo_root_manifest_path, mapping[env], use_branches, append_project, teams_config)
                    output_file = Path(repo_name+'/templates/'+env+'.yaml')
                    output_file.parent.mkdir(exist_ok=True, parents=True)
                    output_file.write_text(yaml)
            else:
                print('skiped item due to missing mandatory fields:' + item )
except Exception as error:
    print('Cought exception:', error)
    sys.exit(1)
