"""
LLM-Based Agent Coordinator for Federated Learning

Provides intelligent coordination, threat assessment, and adaptive decision-making
using Large Language Models via OpenRouter.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient as OpenRouterClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FLAgentCoordinator:
    """
    Intelligent FL coordinator using LLM for decision-making.
    
    Capabilities:
    - Real-time threat assessment
    - Adaptive aggregation strategy selection
    - Incident response coordination
    - System health monitoring
    - Automated reporting
    """
    
    def __init__(
        self,
        llm_client: Optional[OpenRouterClient] = None,
        enable_auto_response: bool = False
    ):
        """
        Initialize FL agent coordinator.
        
        Args:
            llm_client: OpenRouter client (creates default if None)
            enable_auto_response: Allow automated responses to threats
        """
        self.llm = llm_client or OpenRouterClient()
        self.enable_auto_response = enable_auto_response
        
        self.threat_history = []
        self.actions_taken = []
        self.system_state = {
            "status": "operational",
            "threat_level": "low",
            "last_assessment": None
        }
        
        logger.info("FL Agent Coordinator initialized")
        logger.info(f"Auto-response: {'enabled' if enable_auto_response else 'disabled'}")
    
    def assess_fl_round(
        self,
        round_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess FL round using LLM intelligence.
        
        Args:
            round_data: {
                'round_number': int,
                'participating_nodes': int,
                'trust_scores': dict,
                'anomalies_detected': list,
                'metrics': dict
            }
            
        Returns:
            Assessment with recommendations
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"LLM Assessment - Round {round_data.get('round_number', 'N/A')}")
        logger.info(f"{'='*70}")
        
        # Prepare event data for LLM
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "round": round_data.get('round_number'),
            "nodes": round_data.get('participating_nodes'),
            "trust_avg": sum(round_data.get('trust_scores', {}).values()) / max(len(round_data.get('trust_scores', {})), 1),
            "anomalies": len(round_data.get('anomalies_detected', [])),
            "accuracy": round_data.get('metrics', {}).get('accuracy', 0)
        }
        
        # Get LLM analysis
        analysis = self.llm.analyze_security_event(event_data)
        
        logger.info(f"Threat Level: {analysis.get('threat_level', 'unknown').upper()}")
        logger.info(f"Recommended Action: {analysis.get('action', 'none')}")
        logger.info(f"Confidence: {analysis.get('confidence', 0):.2f}")
        logger.info(f"Reasoning: {analysis.get('reasoning', 'N/A')}")
        
        # Update system state
        self.system_state['threat_level'] = analysis.get('threat_level', 'unknown')
        self.system_state['last_assessment'] = datetime.now()
        
        # Store in history
        self.threat_history.append({
            "timestamp": datetime.now(),
            "round": round_data.get('round_number'),
            "analysis": analysis
        })
        
        return analysis
    
    def select_aggregation_strategy(
        self,
        round_stats: Dict[str, Any],
        current_strategy: str = "fedavg"
    ) -> str:
        """
        Use LLM to select optimal aggregation strategy.
        
        Args:
            round_stats: Current round statistics
            current_strategy: Current aggregation method
            
        Returns:
            Recommended strategy
        """
        logger.info("\n🤖 LLM: Selecting aggregation strategy...")
        
        # Add current strategy to stats
        round_stats['current_strategy'] = current_strategy
        
        # Get LLM recommendation
        recommended = self.llm.recommend_aggregation_strategy(round_stats)
        
        if recommended != current_strategy:
            logger.info(f"✨ LLM RECOMMENDATION: Switch to '{recommended}'")
            logger.info(f"   (Current: '{current_strategy}')")
        else:
            logger.info(f"✓ LLM: Continue with '{current_strategy}'")
        
        return recommended
    
    def handle_security_incident(
        self,
        incident: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Coordinate response to security incident.
        
        Args:
            incident: Incident details
            
        Returns:
            Response actions
        """
        logger.warning(f"\n⚠️  SECURITY INCIDENT DETECTED")
        logger.warning(f"{'='*70}")
        
        # Assess threat
        assessment = self.llm.analyze_security_event(incident)
        
        # Determine response
        response = {
            "timestamp": datetime.now().isoformat(),
            "incident": incident,
            "assessment": assessment,
            "actions": []
        }
        
        threat_level = assessment.get('threat_level', 'unknown')
        
        # Low threat
        if threat_level == 'low':
            response['actions'] = ['log_incident', 'monitor']
            logger.info("Action: Monitor and log")
        
        # Medium threat
        elif threat_level == 'medium':
            response['actions'] = ['increase_monitoring', 'alert_admin', 'switch_to_secure_aggregation']
            logger.warning("Action: Enhanced monitoring + secure aggregation")
        
        # High threat
        elif threat_level == 'high':
            response['actions'] = ['quarantine_suspicious_nodes', 'switch_to_krum', 'alert_admin', 'generate_report']
            logger.error("Action: QUARANTINE + Maximum security mode")
        
        # Auto-response if enabled
        if self.enable_auto_response:
            logger.info("Auto-response ENABLED - executing actions")
            self._execute_response_actions(response['actions'])
        else:
            logger.info("Auto-response DISABLED - actions logged for manual review")
        
        # Store action
        self.actions_taken.append(response)
        
        # Generate incident report
        if 'generate_report' in response['actions']:
            report = self.llm.generate_incident_report(incident)
            response['report'] = report
            logger.info(f"\nIncident Report:\n{report}")
        
        return response
    
    def _execute_response_actions(self, actions: List[str]):
        """Execute automated response actions"""
        for action in actions:
            logger.info(f"  Executing: {action}")
            # In production, these would trigger actual system changes
            # For now, just log
    
    def generate_health_report(
        self,
        system_metrics: Dict[str, Any]
    ) -> str:
        """
        Generate system health report using LLM.
        
        Args:
            system_metrics: Current system metrics
            
        Returns:
            Health report
        """
        logger.info("\n📊 Generating System Health Report...")
        
        report_data = {
            "timestamp": datetime.now().isoformat(),  # Convert to string
            "metrics": system_metrics,
            "recent_threats": len([
                t for t in self.threat_history[-10:]
                if t['analysis'].get('threat_level') != 'low'
            ]),
            "actions_taken": len(self.actions_taken),
            "system_state": self.system_state
        }
        
        report = self.llm.generate_incident_report(report_data)
        
        logger.info(f"\n{report}")
        
        return report
    
    def get_intelligent_summary(self) -> Dict[str, Any]:
        """Get intelligent summary of FL session"""
        return {
            "total_assessments": len(self.threat_history),
            "high_threats": len([t for t in self.threat_history if t['analysis'].get('threat_level') == 'high']),
            "medium_threats": len([t for t in self.threat_history if t['analysis'].get('threat_level') == 'medium']),
            "actions_taken": len(self.actions_taken),
            "current_status": self.system_state['status'],
            "current_threat_level": self.system_state['threat_level']
        }
    
    def summary(self):
        """Print coordinator summary"""
        logger.info("\n" + "="*70)
        logger.info("LLM AGENT COORDINATOR SUMMARY")
        logger.info("="*70)
        
        summary = self.get_intelligent_summary()
        
        logger.info(f"Total LLM assessments: {summary['total_assessments']}")
        logger.info(f"High threats detected: {summary['high_threats']}")
        logger.info(f"Medium threats detected: {summary['medium_threats']}")
        logger.info(f"Automated actions: {summary['actions_taken']}")
        logger.info(f"Current status: {summary['current_status']}")
        logger.info(f"Threat level: {summary['current_threat_level'].upper()}")
        
        logger.info("="*70)
