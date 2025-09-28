"""
Comprehensive Monitoring and Metrics System for Smart Database
Provides logging, performance metrics, health checks, and observability
"""

import time
import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import psutil
import traceback
from functools import wraps
from contextlib import asynccontextmanager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smart_database.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    timestamp: datetime
    value: float
    tags: Dict[str, str] = None

@dataclass
class PerformanceMetric:
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = None

@dataclass
class ErrorMetric:
    timestamp: datetime
    error_type: str
    service: str
    message: str
    traceback: str
    user_id: Optional[str] = None

@dataclass
class HealthStatus:
    service: str
    status: str  # healthy, unhealthy, degraded
    message: str
    timestamp: datetime
    response_time: Optional[float] = None

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.performance_metrics: deque = deque(maxlen=1000)
        self.error_metrics: deque = deque(maxlen=500)
        self.health_statuses: Dict[str, HealthStatus] = {}
        self.start_time = datetime.now()

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric value"""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        self.metrics[name].append(point)
        
        logger.debug(f"Metric recorded: {name}={value} {tags}")

    def record_performance(self, name: str, duration: float, unit: str = "seconds", tags: Dict[str, str] = None):
        """Record performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=duration,
            unit=unit,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.performance_metrics.append(metric)
        
        # Also record as regular metric for aggregation
        self.record_metric(f"performance.{name}", duration, tags)

    def record_error(self, error: Exception, service: str, user_id: Optional[str] = None):
        """Record error occurrence"""
        error_metric = ErrorMetric(
            timestamp=datetime.now(),
            error_type=type(error).__name__,
            service=service,
            message=str(error),
            traceback=traceback.format_exc(),
            user_id=user_id
        )
        self.error_metrics.append(error_metric)
        
        # Record error count metric
        self.record_metric(
            "errors.count",
            1,
            {"error_type": error_metric.error_type, "service": service}
        )
        
        logger.error(f"Error in {service}: {error_metric.error_type} - {error_metric.message}")

    def update_health_status(self, service: str, status: str, message: str, response_time: Optional[float] = None):
        """Update service health status"""
        health = HealthStatus(
            service=service,
            status=status,
            message=message,
            timestamp=datetime.now(),
            response_time=response_time
        )
        self.health_statuses[service] = health
        
        # Record health as metric
        status_value = {"healthy": 1, "degraded": 0.5, "unhealthy": 0}.get(status, 0)
        self.record_metric(
            "health.status",
            status_value,
            {"service": service}
        )

    def get_metrics_summary(self, since_minutes: int = 60) -> Dict[str, Any]:
        """Get metrics summary for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=since_minutes)
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "metrics": {},
            "performance": {},
            "errors": {},
            "health": {}
        }
        
        # Aggregate metrics
        for metric_name, points in self.metrics.items():
            recent_points = [p for p in points if p.timestamp > cutoff_time]
            if recent_points:
                values = [p.value for p in recent_points]
                summary["metrics"][metric_name] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1]
                }
        
        # Performance summary
        recent_perf = [m for m in self.performance_metrics if m.timestamp > cutoff_time]
        perf_by_name = defaultdict(list)
        for metric in recent_perf:
            perf_by_name[metric.name].append(metric.value)
        
        for name, values in perf_by_name.items():
            summary["performance"][name] = {
                "count": len(values),
                "avg_ms": (sum(values) / len(values)) * 1000,
                "min_ms": min(values) * 1000,
                "max_ms": max(values) * 1000,
                "p95_ms": sorted(values)[int(len(values) * 0.95)] * 1000 if values else 0
            }
        
        # Error summary
        recent_errors = [e for e in self.error_metrics if e.timestamp > cutoff_time]
        error_by_type = defaultdict(int)
        error_by_service = defaultdict(int)
        
        for error in recent_errors:
            error_by_type[error.error_type] += 1
            error_by_service[error.service] += 1
        
        summary["errors"] = {
            "total_count": len(recent_errors),
            "by_type": dict(error_by_type),
            "by_service": dict(error_by_service)
        }
        
        # Health summary
        summary["health"] = {
            service: {
                "status": health.status,
                "message": health.message,
                "last_check": health.timestamp.isoformat(),
                "response_time_ms": health.response_time * 1000 if health.response_time else None
            }
            for service, health in self.health_statuses.items()
        }
        
        return summary

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Record system metrics
        self.record_metric("system.cpu_percent", cpu_percent)
        self.record_metric("system.memory_percent", memory.percent)
        self.record_metric("system.memory_used_gb", memory.used / (1024**3))
        self.record_metric("system.disk_percent", disk.percent)
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "percent": disk.percent
            }
        }

class PerformanceMonitor:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector

    @asynccontextmanager
    async def measure_async(self, operation_name: str, tags: Dict[str, str] = None):
        """Context manager for measuring async operation performance"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.metrics_collector.record_performance(operation_name, duration, tags=tags)

    def measure_sync(self, operation_name: str, tags: Dict[str, str] = None):
        """Context manager for measuring sync operation performance"""
        class SyncMeasure:
            def __init__(self, monitor, name, tags):
                self.monitor = monitor
                self.name = name
                self.tags = tags
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.monitor.metrics_collector.record_performance(self.name, duration, tags=self.tags)

        return SyncMeasure(self, operation_name, tags)

def monitor_performance(operation_name: str, tags: Dict[str, str] = None):
    """Decorator for monitoring function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with performance_monitor.measure_async(operation_name, tags):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with performance_monitor.measure_sync(operation_name, tags):
                return func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def monitor_errors(service_name: str):
    """Decorator for monitoring function errors"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                metrics_collector.record_error(e, service_name)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                metrics_collector.record_error(e, service_name)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

class HealthChecker:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.checks: Dict[str, Callable] = {}

    def register_check(self, service_name: str, check_func: Callable):
        """Register a health check function"""
        self.checks[service_name] = check_func

    async def run_all_checks(self) -> Dict[str, HealthStatus]:
        """Run all registered health checks"""
        results = {}
        
        for service_name, check_func in self.checks.items():
            try:
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(check_func):
                    check_result = await check_func()
                else:
                    check_result = check_func()
                
                response_time = time.time() - start_time
                
                if isinstance(check_result, dict):
                    status = check_result.get("status", "unknown")
                    message = check_result.get("message", "")
                else:
                    status = "healthy" if check_result else "unhealthy"
                    message = "Health check passed" if check_result else "Health check failed"
                
                self.metrics_collector.update_health_status(
                    service_name, status, message, response_time
                )
                results[service_name] = self.metrics_collector.health_statuses[service_name]
                
            except Exception as e:
                self.metrics_collector.record_error(e, f"health_check_{service_name}")
                self.metrics_collector.update_health_status(
                    service_name, "unhealthy", f"Health check failed: {str(e)}"
                )
                results[service_name] = self.metrics_collector.health_statuses[service_name]
        
        return results

class AlertManager:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: List[Dict] = []
        self.active_alerts: Dict[str, datetime] = {}

    def add_alert_rule(self, name: str, condition: Callable, message: str, cooldown_minutes: int = 5):
        """Add an alert rule"""
        self.alert_rules.append({
            "name": name,
            "condition": condition,
            "message": message,
            "cooldown_minutes": cooldown_minutes
        })

    async def check_alerts(self):
        """Check all alert rules and trigger alerts if needed"""
        current_time = datetime.now()
        
        for rule in self.alert_rules:
            rule_name = rule["name"]
            
            # Check cooldown
            if rule_name in self.active_alerts:
                time_since_last = current_time - self.active_alerts[rule_name]
                if time_since_last.total_seconds() < rule["cooldown_minutes"] * 60:
                    continue
            
            # Evaluate condition
            try:
                if rule["condition"](self.metrics_collector):
                    await self._trigger_alert(rule_name, rule["message"])
                    self.active_alerts[rule_name] = current_time
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule_name}: {str(e)}")

    async def _trigger_alert(self, alert_name: str, message: str):
        """Trigger an alert (can be extended to send notifications)"""
        logger.warning(f"ALERT: {alert_name} - {message}")
        
        # Record alert as metric
        self.metrics_collector.record_metric(
            "alerts.triggered",
            1,
            {"alert_name": alert_name}
        )

# Global instances
metrics_collector = MetricsCollector()
performance_monitor = PerformanceMonitor(metrics_collector)
health_checker = HealthChecker(metrics_collector)
alert_manager = AlertManager(metrics_collector)

# Setup default alert rules
def setup_default_alerts():
    """Setup default monitoring alerts"""
    
    def high_error_rate(collector):
        recent_errors = [e for e in collector.error_metrics 
                        if e.timestamp > datetime.now() - timedelta(minutes=5)]
        return len(recent_errors) > 10
    
    def high_memory_usage(collector):
        system_metrics = collector.get_system_metrics()
        return system_metrics["memory"]["percent"] > 90
    
    def service_unhealthy(collector):
        unhealthy_services = [
            name for name, health in collector.health_statuses.items()
            if health.status == "unhealthy"
        ]
        return len(unhealthy_services) > 0
    
    alert_manager.add_alert_rule(
        "high_error_rate",
        high_error_rate,
        "High error rate detected: >10 errors in 5 minutes"
    )
    
    alert_manager.add_alert_rule(
        "high_memory_usage",
        high_memory_usage,
        "High memory usage detected: >90%"
    )
    
    alert_manager.add_alert_rule(
        "service_unhealthy",
        service_unhealthy,
        "One or more services are unhealthy"
    )

# Initialize default alerts
setup_default_alerts()

# Monitoring utilities
async def start_monitoring_loop(interval_seconds: int = 60):
    """Start background monitoring loop"""
    while True:
        try:
            # Run health checks
            await health_checker.run_all_checks()
            
            # Collect system metrics
            metrics_collector.get_system_metrics()
            
            # Check alerts
            await alert_manager.check_alerts()
            
            await asyncio.sleep(interval_seconds)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(interval_seconds) 