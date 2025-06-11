import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Filter, 
  Search, 
  MoreVertical, 
  Play, 
  Pause, 
  Trash2, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  XCircle,
  Eye
} from 'lucide-react';
import { CrawlJob } from '../types';
import { CUSTOMER_ENDPOINTS } from '../config';
import { useAuth } from '../contexts/AuthContext';

const Jobs: React.FC = () => {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedJobs, setSelectedJobs] = useState<string[]>([]);

  // Mock data - replace with actual API calls
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const mockJobs: CrawlJob[] = [
          {
            id: '1',
            target_url: 'https://example.com',
            job_type: 'link_analysis',
            status: 'COMPLETED',
            progress_percentage: 100,
            urls_crawled: 247,
            links_found: 1843,
            errors: [],
            priority: 1,
            created_at: '2025-06-10T08:30:00Z',
            started_date: '2025-06-10T08:31:00Z',
            completed_date: '2025-06-10T09:15:00Z'
          },
          {
            id: '2',
            target_url: 'https://competitor.com',
            job_type: 'competitive_analysis',
            status: 'IN_PROGRESS',
            progress_percentage: 65,
            urls_crawled: 156,
            links_found: 892,
            errors: [],
            priority: 2,
            created_at: '2025-06-10T10:00:00Z',
            started_date: '2025-06-10T10:02:00Z'
          },
          {
            id: '3',
            target_url: 'https://newdomain.org',
            job_type: 'domain_analysis',
            status: 'QUEUED',
            progress_percentage: 0,
            urls_crawled: 0,
            links_found: 0,
            errors: [],
            priority: 3,
            created_at: '2025-06-10T11:30:00Z'
          },
          {
            id: '4',
            target_url: 'https://failed-site.net',
            job_type: 'crawl',
            status: 'FAILED',
            progress_percentage: 25,
            urls_crawled: 45,
            links_found: 123,
            errors: [
              {
                error_type: 'CONNECTION_ERROR',
                message: 'Unable to connect to target domain',
                timestamp: '2025-06-10T07:45:00Z'
              }
            ],
            priority: 1,
            created_at: '2025-06-10T07:30:00Z',
            started_date: '2025-06-10T07:31:00Z'
          }
        ];
        
        setJobs(mockJobs);
      } catch (error) {
        console.error('Failed to fetch jobs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchJobs();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="h-5 w-5 text-success" />;
      case 'IN_PROGRESS':
        return <Clock className="h-5 w-5 text-warning" />;
      case 'QUEUED':
        return <Clock className="h-5 w-5 text-info" />;
      case 'FAILED':
        return <XCircle className="h-5 w-5 text-error" />;
      case 'CANCELLED':
        return <AlertCircle className="h-5 w-5 text-neutral-500" />;
      default:
        return <Clock className="h-5 w-5 text-neutral-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'status-success';
      case 'IN_PROGRESS':
        return 'status-warning';
      case 'QUEUED':
        return 'status-info';
      case 'FAILED':
        return 'status-error';
      case 'CANCELLED':
        return 'status-neutral';
      default:
        return 'status-neutral';
    }
  };

  const filteredJobs = jobs.filter(job => {
    const matchesSearch = job.target_url.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         job.job_type.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || job.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleSelectJob = (jobId: string) => {
    setSelectedJobs(prev => 
      prev.includes(jobId) 
        ? prev.filter(id => id !== jobId)
        : [...prev, jobId]
    );
  };

  const handleSelectAll = () => {
    setSelectedJobs(
      selectedJobs.length === filteredJobs.length 
        ? [] 
        : filteredJobs.map(job => job.id)
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="spinner-lg mx-auto mb-4"></div>
          <p className="text-neutral-600">Loading jobs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Jobs</h1>
          <p className="text-neutral-600">Manage your crawl and analysis jobs</p>
        </div>
        <button className="btn-primary">
          <Plus className="h-4 w-4 mr-2" />
          New Job
        </button>
      </div>

      {/* Filters and Search */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <input
                  type="text"
                  placeholder="Search jobs by URL or type..."
                  className="form-input pl-10"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            {/* Status Filter */}
            <div className="sm:w-48">
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="QUEUED">Queued</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="COMPLETED">Completed</option>
                <option value="FAILED">Failed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>

            {/* Filter Button */}
            <button className="btn-secondary">
              <Filter className="h-4 w-4 mr-2" />
              More Filters
            </button>
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  className="form-checkbox"
                  checked={selectedJobs.length === filteredJobs.length && filteredJobs.length > 0}
                  onChange={handleSelectAll}
                />
                <span className="ml-2 text-sm text-neutral-600">
                  {selectedJobs.length > 0 ? `${selectedJobs.length} selected` : 'Select all'}
                </span>
              </label>
            </div>
            {selectedJobs.length > 0 && (
              <div className="flex items-center space-x-2">
                <button className="btn-secondary btn-sm">
                  <Pause className="h-4 w-4 mr-1" />
                  Pause
                </button>
                <button className="btn-error btn-sm">
                  <Trash2 className="h-4 w-4 mr-1" />
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="table">
            <thead className="table-header">
              <tr>
                <th className="table-header-cell w-4"></th>
                <th className="table-header-cell">Target URL</th>
                <th className="table-header-cell">Type</th>
                <th className="table-header-cell">Status</th>
                <th className="table-header-cell">Progress</th>
                <th className="table-header-cell">Results</th>
                <th className="table-header-cell">Created</th>
                <th className="table-header-cell">Actions</th>
              </tr>
            </thead>
            <tbody className="table-body">
              {filteredJobs.map((job) => (
                <tr key={job.id} className="table-row">
                  <td className="table-cell">
                    <input
                      type="checkbox"
                      className="form-checkbox"
                      checked={selectedJobs.includes(job.id)}
                      onChange={() => handleSelectJob(job.id)}
                    />
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center">
                      <div>
                        <div className="text-sm font-medium text-neutral-900">
                          {job.target_url}
                        </div>
                        <div className="text-xs text-neutral-500">
                          ID: {job.id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    <span className="status-neutral capitalize">
                      {job.job_type.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(job.status)}
                      <span className={getStatusBadge(job.status)}>
                        {job.status}
                      </span>
                    </div>
                  </td>
                  <td className="table-cell">
                    <div className="w-full">
                      <div className="flex items-center justify-between text-xs text-neutral-600 mb-1">
                        <span>{job.progress_percentage}%</span>
                        {job.status === 'IN_PROGRESS' && (
                          <span>{job.urls_crawled} URLs</span>
                        )}
                      </div>
                      <div className="progress-bar">
                        <div 
                          className={`progress-fill ${
                            job.status === 'COMPLETED' ? 'bg-success' :
                            job.status === 'FAILED' ? 'bg-error' :
                            job.status === 'IN_PROGRESS' ? 'bg-warning' :
                            'bg-neutral-300'
                          }`}
                          style={{ width: `${job.progress_percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    <div className="text-sm">
                      <div className="text-neutral-900">
                        {job.links_found.toLocaleString()} links
                      </div>
                      <div className="text-xs text-neutral-500">
                        {job.urls_crawled} pages crawled
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    <div className="text-sm text-neutral-600">
                      {new Date(job.created_at).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-neutral-500">
                      {new Date(job.created_at).toLocaleTimeString()}
                    </div>
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center space-x-2">
                      <button className="btn-ghost btn-sm">
                        <Eye className="h-4 w-4" />
                      </button>
                      {job.status === 'IN_PROGRESS' && (
                        <button className="btn-ghost btn-sm">
                          <Pause className="h-4 w-4" />
                        </button>
                      )}
                      {job.status === 'QUEUED' && (
                        <button className="btn-ghost btn-sm">
                          <Play className="h-4 w-4" />
                        </button>
                      )}
                      <button className="btn-ghost btn-sm">
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {filteredJobs.length === 0 && (
          <div className="text-center py-12">
            <Briefcase className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-neutral-900 mb-2">No jobs found</h3>
            <p className="text-neutral-600 mb-6">
              {searchTerm || statusFilter !== 'all' 
                ? 'Try adjusting your search or filters'
                : 'Get started by creating your first job'
              }
            </p>
            <button className="btn-primary">
              <Plus className="h-4 w-4 mr-2" />
              Create New Job
            </button>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      {filteredJobs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-neutral-900">
                {filteredJobs.length}
              </div>
              <div className="text-sm text-neutral-600">Total Jobs</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-warning">
                {filteredJobs.filter(j => j.status === 'IN_PROGRESS').length}
              </div>
              <div className="text-sm text-neutral-600">In Progress</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-success">
                {filteredJobs.filter(j => j.status === 'COMPLETED').length}
              </div>
              <div className="text-sm text-neutral-600">Completed</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-brand-primary">
                {filteredJobs.reduce((sum, job) => sum + job.links_found, 0).toLocaleString()}
              </div>
              <div className="text-sm text-neutral-600">Links Found</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Jobs;
