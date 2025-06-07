import React, { useState, useEffect } from 'react';
import { User } from '../types'; // Import User type
import { getCrawlJobs } from '../services/api'; // Import API service

// Define a type for a single job
interface CrawlJob {
  id: string;
  targetUrl: string;
  status: string;
  progress: number;
  created: string;
}

interface CrawlJobsProps {
  user: User | null; // User can be null if not logged in yet
}

const CrawlJobs: React.FC<CrawlJobsProps> = ({ user }) => {
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // In a real application, you'd fetch data from your backend API
        // const data = await getCrawlJobs(user.id); 
        
        // Simulate API call
        const data = await getCrawlJobs(); // Use the imported API service
        setJobs(data);
      } catch (err: any) {
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
    return <div className="text-center text-nasa-light-gray text-xl mt-20">Loading crawl jobs...</div>;
  }

  if (error) {
    return <div className="text-center text-red-500 text-xl mt-20">{error}</div>;
  }

  if (jobs.length === 0) {
    return <div className="text-center text-nasa-light-gray text-xl mt-20">No crawl jobs found for your account.</div>;
  }

  return (
    <div className="p-6">
      <h2 className="text-3xl font-bold text-nasa-cyan mb-4">Your Crawl Jobs</h2>
      <p className="text-nasa-light-gray mb-6">Here you can view the status and details of all your submitted crawl jobs.</p>

      <div className="overflow-x-auto bg-nasa-gray rounded-lg shadow-lg border border-nasa-cyan">
        <table className="min-w-full text-left text-nasa-light-gray text-sm">
          <thead>
            <tr className="text-nasa-cyan border-b border-nasa-light-gray">
              <th className="py-3 px-4">Job ID</th>
              <th className="py-3 px-4">Target URL</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Progress</th>
              <th className="py-3 px-4">Created Date</th>
              <th className="py-3 px-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-b border-gray-700 last:border-b-0">
                <td className="py-3 px-4">{job.id}</td>
                <td className="py-3 px-4"><a href={job.targetUrl} target="_blank" rel="noopener noreferrer" className="text-nasa-cyan hover:underline">{job.targetUrl}</a></td>
                <td className="py-3 px-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    job.status === 'Completed' ? 'bg-green-500 text-white' :
                    job.status === 'In Progress' ? 'bg-nasa-amber text-nasa-dark-blue' :
                    job.status === 'Failed' ? 'bg-red-500 text-white' :
                    'bg-gray-500 text-white'
                  }`}>
                    {job.status}
                  </span>
                </td>
                <td className="py-3 px-4">{job.progress}%</td>
                <td className="py-3 px-4">{job.created}</td>
                <td className="py-3 px-4 space-x-2">
                  <button className="btn-secondary btn-xs">View Details</button>
                  {job.status === 'In Progress' || job.status === 'Pending' ? (
                    <button className="btn-danger btn-xs">Cancel</button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 text-right">
        <button className="btn-primary">Submit New Crawl Job</button>
      </div>
    </div>
  );
};

export default CrawlJobs;
