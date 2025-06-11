import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Briefcase, 
  FileText, 
  BarChart3, 
  Plus,
  ExternalLink,
  Clock,
  CheckCircle,
  AlertCircle,
  Target
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { DashboardStats, RecentActivity, QuickAction } from '../types';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Mock data - replace with actual API calls
  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        setStats({
          total_jobs: 45,
          active_jobs: 3,
          completed_jobs_today: 7,
          total_backlinks_discovered: 12847,
          domains_analyzed: 156,
          average_authority_score: 72.5,
          recent_activity: [
            {
              id: '1',
              type: 'job_completed',
              title: 'Link Analysis Completed',
              description: 'example.com analysis finished with 347 backlinks found',
              timestamp: '2025-06-10T10:30:00Z',
              status: 'success'
            },
            {
              id: '2',
              type: 'report_generated',
              title: 'SEO Report Generated',
              description: 'Competitive analysis report for techstartup.io',
              timestamp: '2025-06-10T09:15:00Z',
              status: 'success'
            },
            {
              id: '3',
              type: 'analysis_finished',
              title: 'Domain Analysis Complete',
              description: 'competitor-site.com domain metrics updated',
              timestamp: '2025-06-10T08:45:00Z',
              status: 'success'
            }
          ]
        });
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const quickActions: QuickAction[] = [
    {
      id: 'link-analysis',
      title: 'Link Analysis',
      description: 'Analyze backlinks for any domain',
      icon: 'ExternalLink',
      action: () => console.log('Start link analysis')
    },
    {
      id: 'domain-audit',
      title: 'Domain Audit',
      description: 'Comprehensive domain health check',
      icon: 'Target',
      action: () => console.log('Start domain audit')
    },
    {
      id: 'competitive-analysis',
      title: 'Competitive Analysis',
      description: 'Compare against competitors',
      icon: 'BarChart3',
      action: () => console.log('Start competitive analysis')
    },
    {
      id: 'create-report',
      title: 'Generate Report',
      description: 'Create custom SEO report',
      icon: 'FileText',
      action: () => console.log('Create report')
    }
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="spinner-lg mx-auto mb-4"></div>
          <p className="text-neutral-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="bg-gradient-to-r from-brand-primary to-brand-secondary rounded-xl p-6 text-white">
        <h1 className="text-2xl font-bold mb-2">
          Welcome back, {user?.username}!
        </h1>
        <p className="text-brand-light">
          Track your SEO performance and manage your link analysis projects.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {quickActions.map((action) => (
          <button
            key={action.id}
            onClick={action.action}
            className="card hover:shadow-md transition-shadow duration-200 text-left group"
          >
            <div className="card-body">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-brand-light rounded-lg flex items-center justify-center group-hover:bg-brand-primary group-hover:text-white transition-colors">
                  {action.icon === 'ExternalLink' && <ExternalLink className="h-5 w-5" />}
                  {action.icon === 'Target' && <Target className="h-5 w-5" />}
                  {action.icon === 'BarChart3' && <BarChart3 className="h-5 w-5" />}
                  {action.icon === 'FileText' && <FileText className="h-5 w-5" />}
                </div>
                <Plus className="h-4 w-4 text-neutral-400 group-hover:text-brand-primary transition-colors" />
              </div>
              <h3 className="font-semibold text-neutral-900 mb-1">{action.title}</h3>
              <p className="text-sm text-neutral-600">{action.description}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Total Jobs</p>
                <p className="text-2xl font-bold text-neutral-900">{stats?.total_jobs}</p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <Briefcase className="h-6 w-6 text-blue-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+12%</span>
              <span className="text-neutral-600 ml-1">from last month</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Active Jobs</p>
                <p className="text-2xl font-bold text-neutral-900">{stats?.active_jobs}</p>
              </div>
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                <Clock className="h-6 w-6 text-yellow-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <span className="text-neutral-600">Currently in progress</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Backlinks Found</p>
                <p className="text-2xl font-bold text-neutral-900">{stats?.total_backlinks_discovered.toLocaleString()}</p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <ExternalLink className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="h-4 w-4 text-success mr-1" />
              <span className="text-success font-medium">+847</span>
              <span className="text-neutral-600 ml-1">this week</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-neutral-600">Avg Authority</p>
                <p className="text-2xl font-bold text-neutral-900">{stats?.average_authority_score}</p>
              </div>
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="h-6 w-6 text-purple-600" />
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

      {/* Recent Activity & Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Recent Activity</h3>
          </div>
          <div className="card-body">
            <div className="space-y-4">
              {stats?.recent_activity.map((activity) => (
                <div key={activity.id} className="flex items-start space-x-3">
                  <div className="flex-shrink-0">
                    {activity.status === 'success' && (
                      <CheckCircle className="h-5 w-5 text-success" />
                    )}
                    {activity.status === 'warning' && (
                      <AlertCircle className="h-5 w-5 text-warning" />
                    )}
                    {activity.status === 'error' && (
                      <AlertCircle className="h-5 w-5 text-error" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-900">
                      {activity.title}
                    </p>
                    <p className="text-sm text-neutral-600">
                      {activity.description}
                    </p>
                    <p className="text-xs text-neutral-500 mt-1">
                      {new Date(activity.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-neutral-200">
              <button className="text-sm text-brand-primary hover:text-brand-secondary font-medium">
                View all activity →
              </button>
            </div>
          </div>
        </div>

        {/* Today's Completion */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-neutral-900">Today's Progress</h3>
          </div>
          <div className="card-body">
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-neutral-700">Jobs Completed</span>
                  <span className="text-sm text-neutral-600">{stats?.completed_jobs_today}/10</span>
                </div>
                <div className="progress-bar">
                  <div 
                    className="progress-primary" 
                    style={{ width: `${(stats?.completed_jobs_today || 0) * 10}%` }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-neutral-700">Domains Analyzed</span>
                  <span className="text-sm text-neutral-600">8/15</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-success" style={{ width: '53%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-neutral-700">Reports Generated</span>
                  <span className="text-sm text-neutral-600">3/5</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-warning" style={{ width: '60%' }}></div>
                </div>
              </div>
            </div>

            <div className="mt-6 p-4 bg-brand-light rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-brand-primary">Productivity Score</p>
                  <p className="text-2xl font-bold text-brand-primary">85%</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-brand-primary">Great work!</p>
                  <p className="text-xs text-brand-primary opacity-75">Above average</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
