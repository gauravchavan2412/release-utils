#!/usr/bin/env python3
"""
Service Mapping Configuration

This module defines the mapping between service names in .env files 
and their corresponding names in version.json endpoints.
"""

from typing import Dict, Set


class ServiceMapper:
    """Handles mapping between different service naming conventions."""
    
    # Mapping from .env service names (lowercase) to version.json service names
    SERVICE_NAME_MAPPING = {
        # Core services
        "appcd": "appcd",
        "iacgen": "iac-gen", 
        "appcdui": "ui",
        "stack_exporter": "exporter",
        "stackgen_vault": "vault",
        "integrations": "integrations",
        "backstage_adapter": "backstage-adapter",
        "infra_catalog_tracker": "infra-catalog-tracker",
        "deployment_manager": "deployment-manager",
        "stackgen_notifications": "notifications",
        "tf_module_service": "tf-module-service",
        "audit_manager": "audit-manager",
        "sgai_orchestration": "sgai-orchestration",
        
        # Special case services that don't follow standard naming
        "stackgen_notifications": "notifications",
        
        # Services that might be in .env but not in version.json
        "appcd_analyzer": None,  # Not in version.json
        "appcdvira": None,       # Not in version.json
        "llm_gateway": None,     # Not in version.json
        "sgai_knowledge": None,  # Not in version.json
        "sgai_control": None,    # Not in version.json
        "community_infra_gen": None,  # Not in version.json
        "stackgen_subagents": None,   # Not in version.json - might map to agents
    }
    
    # Reverse mapping for version.json services that might not have .env equivalents
    VERSION_JSON_ONLY_SERVICES = {
        "agent-intent-to-iac",
        "agent-iac-filler", 
        "agent-iac-exporter",
        "agent-iac-explainer",
        "agent-iam-fix"
    }
    
    @classmethod
    def map_env_to_deployed(cls, env_service_name: str) -> str:
        """
        Map .env service name to version.json service name.
        
        Args:
            env_service_name: Service name from .env file (lowercase)
            
        Returns:
            Corresponding service name in version.json, or original name if no mapping
        """
        mapped_name = cls.SERVICE_NAME_MAPPING.get(env_service_name.lower())
        if mapped_name is None:
            return None  # Service not present in deployed version
        return mapped_name if mapped_name else env_service_name.lower()
    
    @classmethod
    def get_all_env_services(cls) -> Set[str]:
        """Get all known .env service names."""
        return set(cls.SERVICE_NAME_MAPPING.keys())
    
    @classmethod
    def get_version_json_only_services(cls) -> Set[str]:
        """Get services that only appear in version.json."""
        return cls.VERSION_JSON_ONLY_SERVICES
    
    @classmethod
    def create_unified_comparison(cls, env_versions: Dict[str, str], 
                                 deployed_versions: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """
        Create a unified comparison using proper service name mapping.
        
        Args:
            env_versions: Versions from .env file (service_name -> version)
            deployed_versions: Versions from version.json (service_name -> version)
            
        Returns:
            Dict with structure: {
                service_name: {
                    "env_version": version_or_none,
                    "deployed_version": version_or_none,
                    "env_name": original_env_name,
                    "deployed_name": deployed_service_name
                }
            }
        """
        unified = {}
        
        # Process .env services
        for env_service, env_version in env_versions.items():
            deployed_service = cls.map_env_to_deployed(env_service)
            
            if deployed_service is None:
                # Service only in .env
                unified[env_service] = {
                    "env_version": env_version,
                    "deployed_version": None,
                    "env_name": env_service,
                    "deployed_name": None
                }
            else:
                deployed_version = deployed_versions.get(deployed_service)
                unified[env_service] = {
                    "env_version": env_version,
                    "deployed_version": deployed_version,
                    "env_name": env_service,
                    "deployed_name": deployed_service
                }
        
        # Process deployed services that don't have .env equivalents
        mapped_deployed_services = set()
        for env_service in env_versions.keys():
            deployed_service = cls.map_env_to_deployed(env_service)
            if deployed_service:
                mapped_deployed_services.add(deployed_service)
        
        for deployed_service, deployed_version in deployed_versions.items():
            if deployed_service not in mapped_deployed_services:
                unified[f"deployed_only_{deployed_service}"] = {
                    "env_version": None,
                    "deployed_version": deployed_version,
                    "env_name": None,
                    "deployed_name": deployed_service
                }
        
        return unified


def analyze_sample_data():
    """Analyze the provided sample data to demonstrate mapping."""
    
    # Sample .env data (converted to dict format)
    env_data = {
        "appcd": "v0.65.4",
        "appcd_analyzer": "v0.30.0", 
        "iacgen": "v0.52.6",
        "appcdui": "v0.17.3",
        "appcdvira": "main",
        "llm_gateway": "v0.6.3",
        "stack_exporter": "v0.9.9",
        "stackgen_vault": "v0.5.1",
        "integrations": "v0.12.0",
        "backstage_adapter": "main",
        "tf_module_service": "v0.3.0",
        "infra_catalog_tracker": "v0.3.0",
        "deployment_manager": "v0.4.3",
        "stackgen_notifications": "main",
        "sgai_knowledge": "main",
        "sgai_control": "main",
        "community_infra_gen": "v0.1.1",
        "audit_manager": "v0.0.2",
        "stackgen_subagents": "v0.0.17",
        "sgai_orchestration": "v0.0.6"
    }
    
    # Sample version.json data
    deployed_data = {
        "appcd": "v2025.7.10",
        "iac-gen": "v0.52.6",
        "ui": "v0.17.3",
        "exporter": "v0.9.9",
        "vault": "v0.5.1",
        "integrations": "v0.12.0",
        "backstage-adapter": "",
        "infra-catalog-tracker": "v0.3.0",
        "agent-intent-to-iac": "v0.0.17",
        "agent-iac-filler": "v0.0.17",
        "agent-iac-exporter": "v0.0.17",
        "agent-iac-explainer": "main",
        "agent-iam-fix": "v0.0.17",
        "sgai-orchestration": "v0.0.6",
        "deployment-manager": "v0.4.2",
        "notifications": "main",
        "tf-module-service": "v0.3.0",
        "audit-manager": "v0.0.2"
    }
    
    mapper = ServiceMapper()
    unified = mapper.create_unified_comparison(env_data, deployed_data)
    
    print("SERVICE MAPPING ANALYSIS")
    print("=" * 60)
    
    differences = []
    matches = []
    env_only = []
    deployed_only = []
    
    for service, data in unified.items():
        env_ver = data["env_version"]
        deployed_ver = data["deployed_version"]
        
        if env_ver is None:
            deployed_only.append((service, data))
        elif deployed_ver is None:
            env_only.append((service, data))
        elif env_ver != deployed_ver:
            differences.append((service, data))
        else:
            matches.append((service, data))
    
    print(f"\n✅ MATCHING VERSIONS ({len(matches)}):")
    print("-" * 40)
    for service, data in matches:
        print(f"  {data['env_name']} → {data['deployed_name']}: {data['env_version']}")
    
    print(f"\n⚠️  VERSION DIFFERENCES ({len(differences)}):")
    print("-" * 40)
    for service, data in differences:
        print(f"  {data['env_name']} → {data['deployed_name']}:")
        print(f"    .env: {data['env_version']}")
        print(f"    deployed: {data['deployed_version']}")
        print()
    
    print(f"\n📝 .ENV ONLY SERVICES ({len(env_only)}):")
    print("-" * 40)
    for service, data in env_only:
        print(f"  {data['env_name']}: {data['env_version']} (not in deployed)")
    
    print(f"\n🚀 DEPLOYED ONLY SERVICES ({len(deployed_only)}):")
    print("-" * 40)
    for service, data in deployed_only:
        print(f"  {data['deployed_name']}: {data['deployed_version']} (not in .env)")
    
    return unified


if __name__ == "__main__":
    analyze_sample_data() 