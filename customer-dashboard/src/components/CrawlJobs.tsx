import React, { useState, useEffect } from 'react';
// Assuming you'll have an API service to fetch data
// import { getCrawlJobs } from '../services/api'; 

const CrawlJobs = ({ user }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        setLoading(true);
        setError(null);
        // In a real application, you'd fetch data from your backend API
        // const data = await getCrawlJobs(user.id); 
        
        // Simulate API call
        const simulatedData = [
          { id: 'job-001', targetUrl: 'https://example.com', status: 'Completed', progress: 100, created: '2024-05-01' },
          { id: 'job-002', targetUrl: 'https://anothersite.org', status: 'In Progress', progress: 75, created: '2024-05-10' },
          { id: 'job-003', targetUrl: 'https://testdomain.net', status: 'Failed', progress: 20, created: '2024-05-15' },
          { id: 'job-004', targetUrl: 'https://newsite.io', status: 'Pending', progress: 0, created: '2024-05-20' },
        ];
        setJobs(simulatedData);
      } catch (err) {
        setError('Failed to fetch crawl jobs. Please try again later.');
        console.error('Error fetching crawl jobs:', err);
      } finally {
        setLoading(false);
      }
    };

    if (user) { // Only fetch if user is available
      fetchJobs();
    }
  }, [user]); // Re-fetch if user changes

  if (loading) {
    return <div className="loading-message">Loading crawl jobs...</div>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  if (jobs.length === 0) {
    return <div className="no-data-message">No crawl jobs found for your account.</div>;
  }

  return (
    <div className="crawl-jobs-container">
      <h2>Your Crawl Jobs</h2>
      <p>Here you can view the status and details of all your submitted crawl jobs.</p>

      <table className="jobs-table">
        <thead>
          <tr>
            <th>Job ID</th>
            <th>Target URL</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Created Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{job.id}</td>
              <td><a href={job.targetUrl} target="_blank" rel="noopener noreferrer">{job.targetUrl}</a></td>
              <td><span className={`status-badge status-${job.status.toLowerCase().replace(' ', '-')}`}>{job.status}</span></td>
              <td>{job.progress}%</td>
              <td>{job.created}</td>
              <td>
                <button className="action-button view-details">View Details</button>
                {job.status === 'In Progress' || job.status === 'Pending' ? (
                  <button className="action-button cancel-job">Cancel</button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="jobs-footer">
        <button className="new-job-button">Submit New Crawl Job</button>
      </div>
    </div>
  );
};

export default CrawlJobs;
