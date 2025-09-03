#!/usr/bin/env python3
"""Performance testing script for HyperLiquid Node Parser."""

import asyncio
import aiohttp
import time
import json
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from config.settings import settings

class PerformanceTester:
    """Performance testing utility for the API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_health_endpoint(self) -> dict:
        """Test health endpoint performance."""
        start_time = time.time()
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                response_time = time.time() - start_time
                data = await response.json()
                
                return {
                    "endpoint": "/health",
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": response.status == 200,
                    "data": data
                }
        except Exception as e:
            return {
                "endpoint": "/health",
                "status_code": None,
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def test_performance_endpoint(self) -> dict:
        """Test performance endpoint."""
        start_time = time.time()
        
        try:
            async with self.session.get(f"{self.base_url}/performance") as response:
                response_time = time.time() - start_time
                data = await response.json()
                
                return {
                    "endpoint": "/performance",
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": response.status == 200,
                    "data": data
                }
        except Exception as e:
            return {
                "endpoint": "/performance",
                "status_code": None,
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def test_orders_endpoint(self, limit: int = 100) -> dict:
        """Test orders endpoint with different limits."""
        start_time = time.time()
        
        try:
            url = f"{self.base_url}/api/v1/orders?limit={limit}"
            async with self.session.get(url) as response:
                response_time = time.time() - start_time
                data = await response.json()
                
                return {
                    "endpoint": f"/api/v1/orders?limit={limit}",
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": response.status == 200,
                    "orders_count": len(data) if isinstance(data, list) else 0,
                    "data": data[:3] if isinstance(data, list) and len(data) > 3 else data  # Show first 3 items
                }
        except Exception as e:
            return {
                "endpoint": f"/api/v1/orders?limit={limit}",
                "status_code": None,
                "response_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    async def test_concurrent_requests(self, endpoint: str, concurrent_count: int = 10) -> dict:
        """Test concurrent request handling."""
        start_time = time.time()
        
        async def make_request():
            try:
                async with self.session.get(f"{self.base_url}{endpoint}") as response:
                    await response.json()
                    return {"success": True, "status": response.status}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Create concurrent tasks
        tasks = [make_request() for _ in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        
        return {
            "endpoint": endpoint,
            "concurrent_requests": concurrent_count,
            "total_time": total_time,
            "successful_requests": successful,
            "failed_requests": concurrent_count - successful,
            "requests_per_second": concurrent_count / total_time if total_time > 0 else 0
        }
    
    async def run_full_test_suite(self) -> dict:
        """Run complete performance test suite."""
        print("🚀 Starting performance test suite...")
        print(f"📡 Testing API at: {self.base_url}")
        print("=" * 60)
        
        results = {}
        
        # Test basic endpoints
        print("1️⃣ Testing basic endpoints...")
        results["health"] = await self.test_health_endpoint()
        results["performance"] = await self.test_performance_endpoint()
        
        # Test orders endpoint with different limits
        print("2️⃣ Testing orders endpoint...")
        results["orders_100"] = await self.test_orders_endpoint(100)
        results["orders_1000"] = await self.test_orders_endpoint(1000)
        
        # Test concurrent requests
        print("3️⃣ Testing concurrent requests...")
        results["concurrent_health"] = await self.test_concurrent_requests("/health", 20)
        results["concurrent_orders"] = await self.test_concurrent_requests("/api/v1/orders?limit=100", 10)
        
        return results
    
    def print_results(self, results: dict):
        """Print formatted test results."""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE TEST RESULTS")
        print("=" * 60)
        
        # Basic endpoints
        print("\n🔍 Basic Endpoints:")
        for endpoint, result in [("Health", results["health"]), ("Performance", results["performance"])]:
            status = "✅" if result["success"] else "❌"
            print(f"  {status} {endpoint}: {result['response_time']:.3f}s")
        
        # Orders endpoint
        print("\n📋 Orders Endpoint:")
        for limit, result in [("100", results["orders_100"]), ("1000", results["orders_1000"])]:
            status = "✅" if result["success"] else "❌"
            print(f"  {status} Limit {limit}: {result['response_time']:.3f}s ({result.get('orders_count', 0)} orders)")
        
        # Concurrent requests
        print("\n⚡ Concurrent Requests:")
        for endpoint, result in [("Health", results["concurrent_health"]), ("Orders", results["concurrent_orders"])]:
            status = "✅" if result["successful_requests"] > 0 else "❌"
            success_rate = (result["successful_requests"] / result["concurrent_requests"]) * 100
            print(f"  {status} {endpoint}: {result['requests_per_second']:.1f} req/s, {success_rate:.1f}% success")
        
        # Performance analysis
        print("\n📈 Performance Analysis:")
        health_time = results["health"]["response_time"]
        orders_time = results["orders_100"]["response_time"]
        
        if health_time < 0.1:
            print("  🟢 Health endpoint: Excellent (< 100ms)")
        elif health_time < 0.5:
            print("  🟡 Health endpoint: Good (< 500ms)")
        else:
            print("  🔴 Health endpoint: Slow (> 500ms)")
        
        if orders_time < 0.5:
            print("  🟢 Orders endpoint: Excellent (< 500ms)")
        elif orders_time < 2.0:
            print("  🟡 Orders endpoint: Good (< 2s)")
        else:
            print("  🔴 Orders endpoint: Slow (> 2s)")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if health_time > 1.0:
            print("  - Health endpoint is slow, check system resources")
        if orders_time > 5.0:
            print("  - Orders endpoint is very slow, consider reducing batch sizes")
        if results["concurrent_health"]["requests_per_second"] < 10:
            print("  - Low concurrent request handling, check server configuration")

async def main():
    """Main test function."""
    base_url = "http://localhost:8000"
    
    try:
        async with PerformanceTester(base_url) as tester:
            results = await tester.run_full_test_suite()
            tester.print_results(results)
            
            # Save results to file
            output_file = Path("logs/performance_test_results.json")
            output_file.parent.mkdir(exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"\n💾 Results saved to: {output_file}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
