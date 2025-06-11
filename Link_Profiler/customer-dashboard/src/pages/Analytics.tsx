import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  PieChart, 
  Calendar,
  ExternalLink,
  Target,
  Users,
  Globe
} from 'lucide-react';
import { AnalyticsData, ChartDataPoint } from '../types';

const Analytics: React.FC = () => {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30d');

  // Mock data - replace with actual API calls
  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const mockData: AnalyticsData = {
          date_range: {
            start_date: '2025-05-11T00:00:00Z',
            end_date: '2025-06-10T23:59:59Z'
          },
          metrics: {
            total_jobs: 45,
            completed_jobs: 38,
            failed_jobs: 3,
            total_backlinks_found: 12847,
            unique_domains_analyzed: 156,
            average_authority_score: 72.5
          },
          trends: {
            daily_jobs: [
              { date: '2025-06-04', jobs_created: 2, jobs_completed: 3 },
              { date: '2025-06-05', jobs_created: 4, jobs_completed: 2 },
              { date: '2025-06-06', jobs_created: 1, jobs_completed: 4 },
              { date: '2025-06-07', jobs_created: 3, jobs_completed: 1 },
              { date: '2025-06-08', jobs_created: 2, jobs_completed: 3 },
              { date: '2025-06-09', jobs_created: 5, jobs_completed: 2 },
              { date: '2025-06-10', jobs_created: 3, jobs_completed: 4 }
            ],
            domain_authority_trend: [
              { date: '2025-06-04', average_da: 68.2 },
              { date: '2025-06-05', average_da: 69.1 },
              { date: '2025-06-06', average_da: 70.5 },
              { date: '2025-06-07', average_da: 71.2 },
              { date: '2025-06-08', average_da: 72.0 },
              { date: '2025-06-09', average_da: 72.8 },
              { date: '2025-06-10', average_da: 72.5 }
            ]
          }
        };
        
        setAnalyticsData(mockData);
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [dateRange]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="spinner-lg mx-auto mb-4"></div>
          <p className="text-neutral-600">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (!analyticsData) {
    return (
      <div className="text-center py-12">
        <BarChart3 className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-neutral-900 mb-2">No analytics data available</h3>
        <p className="text-neutral-600">Analytics data will appear here once you start running jobs.</p>
      </div>
    );
  }

  const successRate = analyticsData.metrics.completed_jobs / analyticsData.metrics.total_jobs * 100;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Analytics</h1>
          <p className="text-neutral-600">Track your SEO performance and insights</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            className="form-select"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <button className="btn-secondary">
            <Calendar className="h-4 w-4 mr-2" />
            Custom Range
          </button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Total Jobs</p>
                <p className="text-2xl font-bold text-neutral-900">{analyticsData.metrics.total_jobs}</p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <Target className="h-6 w-6 text-blue-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+12%</span>
              <span className="text-neutral-600 ml-1">vs previous period</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Success Rate</p>
                <p className="text-2xl font-bold text-neutral-900">{successRate.toFixed(1)}%</p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+5.2%</span>
              <span className="text-neutral-600 ml-1">improvement</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Backlinks Found</p>
                <p className="text-2xl font-bold text-neutral-900">{analyticsData.metrics.total_backlinks_found.toLocaleString()}</p>
              </div>
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <ExternalLink className="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+1,247</span>
              <span className="text-neutral-600 ml-1">this period</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Avg Authority</p>
                <p className="text-2xl font-bold text-neutral-900">{analyticsData.metrics.average_authority_score}</p>
              </div>
              <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                <Globe className="h-6 w-6 text-orange-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+2.3</span>
              <span className="text-neutral-600 ml-1">improvement</span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Jobs Trend Chart */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Job Activity Trend</h3>
          </div>
          <div className="card-body">
            <div className="h-64 flex items-center justify-center bg-neutral-50 rounded-lg">
              <div className="text-center">
                <BarChart3 className="h-12 w-12 text-neutral-300 mx-auto mb-2" />
                <p className="text-sm text-neutral-600">Chart component would go here</p>
                <p className="text-xs text-neutral-500">Integration with recharts library</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-lg font-semibold text-brand-primary">
                  {analyticsData.trends.daily_jobs.reduce((sum, day) => sum + day.jobs_created, 0)}
                </div>
                <div className="text-sm text-neutral-600">Jobs Created</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-success">
                  {analyticsData.trends.daily_jobs.reduce((sum, day) => sum + day.jobs_completed, 0)}
                </div>
                <div className="text-sm text-neutral-600">Jobs Completed</div>
              </div>
            </div>
          </div>
        </div>

        {/* Authority Score Trend */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Domain Authority Trend</h3>
          </div>
          <div className="card-body">
            <div className="h-64 flex items-center justify-center bg-neutral-50 rounded-lg">
              <div className="text-center">
                <TrendingUp className="h-12 w-12 text-neutral-300 mx-auto mb-2" />
                <p className="text-sm text-neutral-600">Line chart component would go here</p>
                <p className="text-xs text-neutral-500">Showing authority score progression</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-lg font-semibold text-neutral-900">
                  {analyticsData.trends.domain_authority_trend[0]?.average_da || 0}
                </div>
                <div className="text-sm text-neutral-600">Starting DA</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-success">
                  {analyticsData.trends.domain_authority_trend[analyticsData.trends.domain_authority_trend.length - 1]?.average_da || 0}
                </div>
                <div className="text-sm text-neutral-600">Current DA</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Job Types Distribution */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Job Types</h3>
          </div>
          <div className="card-body">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-neutral-600">Link Analysis</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-neutral-200 rounded-full h-2">
                    <div className="bg-brand-primary h-2 rounded-full" style={{ width: '65%' }}></div>
                  </div>
                  <span className="text-sm font-medium text-neutral-900">65%</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-neutral-600">Domain Analysis</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-neutral-200 rounded-full h-2">
                    <div className="bg-success h-2 rounded-full" style={{ width: '25%' }}></div>
                  </div>
                  <span className="text-sm font-medium text-neutral-900">25%</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-neutral-600">Competitive Analysis</span>
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-neutral-200 rounded-full h-2">
                    <div className="bg-warning h-2 rounded-full" style={{ width: '10%' }}></div>
                  </div>
                  <span className="text-sm font-medium text-neutral-900">10%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Top Performing Domains */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Top Domains</h3>
          </div>
          <div className="card-body">
            <div className="space-y-3">
              {[
                { domain: 'example.com', score: 85, change: '+5' },
                { domain: 'competitor.net', score: 78, change: '+2' },
                { domain: 'newsite.org', score: 72, change: '+8' },
                { domain: 'oldsite.co', score: 68, change: '-1' }
              ].map((item, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-neutral-900">{item.domain}</div>
                    <div className="text-xs text-neutral-500">Authority Score: {item.score}</div>
                  </div>
                  <div className={`text-sm font-medium ${item.change.startsWith('+') ? 'text-success' : 'text-error'}`}>
                    {item.change}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Insights */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Insights</h3>
          </div>
          <div className="card-body">
            <div className="space-y-4">
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="text-sm font-medium text-blue-900">Link Quality Improved</div>
                <div className="text-xs text-blue-700 mt-1">
                  Your average link authority score increased by 12% this month
                </div>
              </div>
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <div className="text-sm font-medium text-green-900">New Opportunities</div>
                <div className="text-xs text-green-700 mt-1">
                  47 new high-authority linking opportunities identified
                </div>
              </div>
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="text-sm font-medium text-yellow-900">Competitive Gap</div>
                <div className="text-xs text-yellow-700 mt-1">
                  Competitors have 23% more backlinks in your niche
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Export Options */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-neutral-900 mb-2">Export Analytics</h3>
              <p className="text-sm text-neutral-600">Download your analytics data for further analysis</p>
            </div>
            <div className="flex items-center space-x-3">
              <button className="btn-secondary">
                Export CSV
              </button>
              <button className="btn-secondary">
                Export PDF Report
              </button>
              <button className="btn-primary">
                Schedule Email Report
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
