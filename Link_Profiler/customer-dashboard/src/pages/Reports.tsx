import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  Filter, 
  Search, 
  Plus, 
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  Eye
} from 'lucide-react';
import { Report } from '../types';

const Reports: React.FC = () => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Mock data - replace with actual API calls
  useEffect(() => {
    const fetchReports = async () => {
      try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const mockReports: Report[] = [
          {
            id: '1',
            title: 'Link Analysis Report - example.com',
            report_type: 'link_analysis',
            status: 'COMPLETED',
            created_at: '2025-06-10T08:30:00Z',
            completed_at: '2025-06-10T09:15:00Z',
            file_url: '/reports/link-analysis-example-com.pdf',
            parameters: { domain: 'example.com', depth: 3 }
          },
          {
            id: '2',
            title: 'Competitive Analysis - Tech Startup Sector',
            report_type: 'competitive_analysis',
            status: 'COMPLETED',
            created_at: '2025-06-09T14:20:00Z',
            completed_at: '2025-06-09T16:45:00Z',
            file_url: '/reports/competitive-analysis-tech.pdf',
            parameters: { competitors: ['competitor1.com', 'competitor2.com'] }
          },
          {
            id: '3',
            title: 'Domain Audit - newsite.org',
            report_type: 'domain_audit',
            status: 'GENERATING',
            created_at: '2025-06-10T11:00:00Z',
            parameters: { domain: 'newsite.org', full_audit: true }
          },
          {
            id: '4',
            title: 'Comprehensive SEO Report - Q2 2025',
            report_type: 'comprehensive',
            status: 'FAILED',
            created_at: '2025-06-08T10:00:00Z',
            parameters: { domains: ['main-site.com'], period: 'Q2-2025' }
          }
        ];
        
        setReports(mockReports);
      } catch (error) {
        console.error('Failed to fetch reports:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchReports();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="h-5 w-5 text-success" />;
      case 'GENERATING':
        return <Clock className="h-5 w-5 text-warning" />;
      case 'PENDING':
        return <Clock className="h-5 w-5 text-info" />;
      case 'FAILED':
        return <AlertCircle className="h-5 w-5 text-error" />;
      default:
        return <Clock className="h-5 w-5 text-neutral-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'status-success';
      case 'GENERATING':
        return 'status-warning';
      case 'PENDING':
        return 'status-info';
      case 'FAILED':
        return 'status-error';
      default:
        return 'status-neutral';
    }
  };

  const getReportTypeLabel = (type: string) => {
    switch (type) {
      case 'link_analysis':
        return 'Link Analysis';
      case 'domain_audit':
        return 'Domain Audit';
      case 'competitive_analysis':
        return 'Competitive Analysis';
      case 'comprehensive':
        return 'Comprehensive Report';
      default:
        return type.replace('_', ' ');
    }
  };

  const filteredReports = reports.filter(report => {
    const matchesSearch = report.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || report.report_type === typeFilter;
    const matchesStatus = statusFilter === 'all' || report.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="spinner-lg mx-auto mb-4"></div>
          <p className="text-neutral-600">Loading reports...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Reports</h1>
          <p className="text-neutral-600">View and download your analysis reports</p>
        </div>
        <button className="btn-primary">
          <Plus className="h-4 w-4 mr-2" />
          Generate Report
        </button>
      </div>

      {/* Filters and Search */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-neutral-400" />
                <input
                  type="text"
                  placeholder="Search reports..."
                  className="form-input pl-10"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
            <div className="sm:w-48">
              <select
                className="form-select"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="all">All Types</option>
                <option value="link_analysis">Link Analysis</option>
                <option value="domain_audit">Domain Audit</option>
                <option value="competitive_analysis">Competitive Analysis</option>
                <option value="comprehensive">Comprehensive</option>
              </select>
            </div>
            <div className="sm:w-48">
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="PENDING">Pending</option>
                <option value="GENERATING">Generating</option>
                <option value="COMPLETED">Completed</option>
                <option value="FAILED">Failed</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredReports.map((report) => (
          <div key={report.id} className="card hover:shadow-md transition-shadow duration-200">
            <div className="card-body">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-brand-light rounded-lg flex items-center justify-center">
                    <FileText className="h-5 w-5 text-brand-primary" />
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusIcon(report.status)}
                    <span className={getStatusBadge(report.status)}>
                      {report.status}
                    </span>
                  </div>
                </div>
              </div>

              <h3 className="font-semibold text-neutral-900 mb-2 line-clamp-2">
                {report.title}
              </h3>

              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-neutral-600">Type:</span>
                  <span className="font-medium text-neutral-900">
                    {getReportTypeLabel(report.report_type)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-neutral-600">Created:</span>
                  <span className="text-neutral-900">
                    {new Date(report.created_at).toLocaleDateString()}
                  </span>
                </div>
                {report.completed_at && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-neutral-600">Completed:</span>
                    <span className="text-neutral-900">
                      {new Date(report.completed_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              <div className="flex items-center space-x-2">
                {report.status === 'COMPLETED' && report.file_url && (
                  <>
                    <button className="btn-primary btn-sm flex-1">
                      <Download className="h-4 w-4 mr-1" />
                      Download
                    </button>
                    <button className="btn-secondary btn-sm">
                      <Eye className="h-4 w-4" />
                    </button>
                  </>
                )}
                {report.status === 'GENERATING' && (
                  <div className="flex-1 text-center py-2">
                    <div className="spinner-sm mx-auto mb-1"></div>
                    <span className="text-xs text-neutral-600">Generating...</span>
                  </div>
                )}
                {report.status === 'FAILED' && (
                  <button className="btn-secondary btn-sm flex-1">
                    Retry Generation
                  </button>
                )}
                {report.status === 'PENDING' && (
                  <div className="flex-1 text-center py-2">
                    <span className="text-xs text-neutral-600">Queued for generation</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredReports.length === 0 && (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 text-neutral-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No reports found</h3>
          <p className="text-neutral-600 mb-6">
            {searchTerm || typeFilter !== 'all' || statusFilter !== 'all'
              ? 'Try adjusting your search or filters'
              : 'Generate your first report to get started'
            }
          </p>
          <button className="btn-primary">
            <Plus className="h-4 w-4 mr-2" />
            Generate Report
          </button>
        </div>
      )}

      {/* Summary Stats */}
      {filteredReports.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-neutral-900">
                {filteredReports.length}
              </div>
              <div className="text-sm text-neutral-600">Total Reports</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-success">
                {filteredReports.filter(r => r.status === 'COMPLETED').length}
              </div>
              <div className="text-sm text-neutral-600">Completed</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-warning">
                {filteredReports.filter(r => r.status === 'GENERATING').length}
              </div>
              <div className="text-sm text-neutral-600">Generating</div>
            </div>
          </div>
          <div className="card">
            <div className="card-body text-center">
              <div className="text-2xl font-bold text-brand-primary">
                {new Date().toLocaleDateString('en-US', { month: 'long' })}
              </div>
              <div className="text-sm text-neutral-600">This Month</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Reports;
