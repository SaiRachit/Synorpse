import time
import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from dotenv import dotenv_values
import json

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    metric_type: str  
    value: float
    context: Dict
    timestamp: datetime


class PerformanceMonitor:
    """
    Track and analyze assistant performance
    """
    
    def __init__(self):
        self._init_db()
        self.session_start = time.time()
        self.session_metrics = {
            'queries_processed': 0,
            'total_response_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'intent_corrections': 0,
            'errors': 0
        }
    
    def _init_db(self):
        """Initialize performance tracking tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id SERIAL PRIMARY KEY,
                    metric_type VARCHAR(100) NOT NULL,
                    value FLOAT NOT NULL,
                    context JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_perf_metric_type ON performance_metrics(metric_type);
                CREATE INDEX IF NOT EXISTS idx_perf_created_at ON performance_metrics(created_at);
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Performance monitor DB init warning: {e}")
    
    def track_query(self, query: str, response_time: float, intent: str, success: bool = True):
        """Track a query execution"""
        self.session_metrics['queries_processed'] += 1
        self.session_metrics['total_response_time'] += response_time
        
        if not success:
            self.session_metrics['errors'] += 1
        
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO performance_metrics (metric_type, value, context) 
                   VALUES (%s, %s, %s)""",
                ('response_time', response_time, Json({
                    'query_length': len(query),
                    'intent': intent,
                    'success': success
                }))
            )
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def track_cache_hit(self, cache_type: str):
        """Track cache hit"""
        self.session_metrics['cache_hits'] += 1
        self._log_metric('cache_hit', 1.0, {'cache_type': cache_type})
    
    def track_cache_miss(self, cache_type: str):
        """Track cache miss"""
        self.session_metrics['cache_misses'] += 1
        self._log_metric('cache_miss', 1.0, {'cache_type': cache_type})
    
    def track_intent_correction(self, original_intent: str, corrected_intent: str):
        """Track when user corrects intent (indicates misclassification)"""
        self.session_metrics['intent_corrections'] += 1
        self._log_metric('intent_correction', 1.0, {
            'original': original_intent,
            'corrected': corrected_intent
        })
    
    def _log_metric(self, metric_type: str, value: float, context: Dict):
        """Log a metric to database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO performance_metrics (metric_type, value, context) 
                   VALUES (%s, %s, %s)""",
                (metric_type, value, Json(context))
            )
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def get_session_stats(self) -> Dict:
        """Get current session statistics"""
        session_duration = time.time() - self.session_start
        queries = self.session_metrics['queries_processed']
        
        avg_response_time = (
            self.session_metrics['total_response_time'] / queries
            if queries > 0 else 0
        )
        
        cache_total = self.session_metrics['cache_hits'] + self.session_metrics['cache_misses']
        cache_hit_rate = (
            (self.session_metrics['cache_hits'] / cache_total * 100)
            if cache_total > 0 else 0
        )
        
        error_rate = (
            (self.session_metrics['errors'] / queries * 100)
            if queries > 0 else 0
        )
        
        return {
            'session_duration_minutes': round(session_duration / 60, 1),
            'queries_processed': queries,
            'avg_response_time_ms': round(avg_response_time * 1000, 2),
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'error_rate': f"{error_rate:.1f}%",
            'intent_corrections': self.session_metrics['intent_corrections']
        }
    
    def get_historical_stats(self, hours: int = 24) -> Dict:
        """Get statistics for the past N hours"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            since = datetime.now() - timedelta(hours=hours)
            
            cur.execute(
                """SELECT AVG(value) FROM performance_metrics 
                   WHERE metric_type = 'response_time' 
                   AND created_at > %s""",
                (since,)
            )
            avg_response = cur.fetchone()[0] or 0
            
            cur.execute(
                """SELECT 
                     SUM(CASE WHEN metric_type = 'cache_hit' THEN 1 ELSE 0 END) as hits,
                     SUM(CASE WHEN metric_type = 'cache_miss' THEN 1 ELSE 0 END) as misses
                   FROM performance_metrics 
                   WHERE metric_type IN ('cache_hit', 'cache_miss')
                   AND created_at > %s""",
                (since,)
            )
            cache_data = cur.fetchone()
            hits, misses = cache_data if cache_data else (0, 0)
            cache_total = hits + misses
            cache_hit_rate = (hits / cache_total * 100) if cache_total > 0 else 0
            
            cur.execute(
                """SELECT COUNT(*) / %s as queries_per_hour
                   FROM performance_metrics 
                   WHERE metric_type = 'response_time'
                   AND created_at > %s""",
                (hours, since)
            )
            queries_per_hour = cur.fetchone()[0] or 0
            
            cur.execute(
                """SELECT COUNT(*) FROM performance_metrics 
                   WHERE metric_type = 'intent_correction'
                   AND created_at > %s""",
                (since,)
            )
            corrections = cur.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'period_hours': hours,
                'avg_response_time_ms': round(avg_response * 1000, 2),
                'cache_hit_rate': f"{cache_hit_rate:.1f}%",
                'queries_per_hour': round(queries_per_hour, 1),
                'total_corrections': corrections
            }
            
        except Exception as e:
            print(f" Error getting historical stats: {e}")
            return {}
    
    def get_slowest_queries(self, limit: int = 10) -> List[Dict]:
        """Get slowest queries for optimization"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT value, context, created_at 
                   FROM performance_metrics 
                   WHERE metric_type = 'response_time'
                   ORDER BY value DESC 
                   LIMIT %s""",
                (limit,)
            )
            
            results = []
            for response_time, context, timestamp in cur.fetchall():
                results.append({
                    'response_time_ms': round(response_time * 1000, 2),
                    'intent': context.get('intent', 'unknown'),
                    'query_length': context.get('query_length', 0),
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            conn.close()
            return results
            
        except Exception as e:
            print(f" Error getting slow queries: {e}")
            return []
    
    def get_intent_accuracy(self, hours: int = 24) -> Dict:
        """Calculate intent classification accuracy"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            since = datetime.now() - timedelta(hours=hours)
            
            # Total queries
            cur.execute(
                """SELECT COUNT(*) FROM performance_metrics 
                   WHERE metric_type = 'response_time'
                   AND created_at > %s""",
                (since,)
            )
            total_queries = cur.fetchone()[0] or 0
            
            cur.execute(
                """SELECT COUNT(*) FROM performance_metrics 
                   WHERE metric_type = 'intent_correction'
                   AND created_at > %s""",
                (since,)
            )
            corrections = cur.fetchone()[0] or 0
            
            conn.close()
            
            accuracy = ((total_queries - corrections) / total_queries * 100) if total_queries > 0 else 100
            
            return {
                'accuracy': f"{accuracy:.1f}%",
                'total_queries': total_queries,
                'misclassifications': corrections
            }
            
        except Exception as e:
            print(f" Error calculating accuracy: {e}")
            return {}
    
    def print_dashboard(self):
        """Print performance dashboard"""
        print("\n" + "="*60)
        print(" PERFORMANCE DASHBOARD")
        print("="*60)
        
        print("\n Current Session:")
        session = self.get_session_stats()
        for key, value in session.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        print("\n Last 24 Hours:")
        historical = self.get_historical_stats(hours=24)
        for key, value in historical.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        print("\n Intent Classification:")
        accuracy = self.get_intent_accuracy(hours=24)
        for key, value in accuracy.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        print("\n Slowest Queries (Top 5):")
        slow = self.get_slowest_queries(limit=5)
        for i, query in enumerate(slow, 1):
            print(f"  {i}. {query['response_time_ms']}ms - {query['intent']} ({query['timestamp']})")
        
        print("\n" + "="*60)
    
    def export_metrics(self, hours: int = 24, filepath: str = "performance_report.json"):
        """Export metrics to JSON file"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'session_stats': self.get_session_stats(),
                'historical_stats': self.get_historical_stats(hours),
                'intent_accuracy': self.get_intent_accuracy(hours),
                'slowest_queries': self.get_slowest_queries(limit=20)
            }
            
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f" Performance report exported to {filepath}")
            return True
            
        except Exception as e:
            print(f" Export failed: {e}")
            return False


_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def track_performance(intent: str):
    """Decorator to automatically track function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                elapsed = time.time() - start_time
                query = args[0] if args else "unknown"
                monitor.track_query(str(query), elapsed, intent, success)
        
        return wrapper
    return decorator