import React from 'react';

const Dashboard = ({ user }) => {
  return (
    <div className="dashboard-container">
      <h2>Welcome to Your Dashboard, {user ? user.username : 'Guest'}!</h2>
      <p>This is your central hub for monitoring your link profiling activities.</p>

      <div className="dashboard-widgets">
        <div className="widget">
          <h3>Recent Crawl Jobs</h3>
          <p>Overview of your latest crawl job statuses.</p>
          {/* Placeholder for a list or table of recent jobs */}
          <ul>
            <li>Job #123 - Completed (example.com)</li>
            <li>Job #124 - In Progress (anothersite.org)</li>
            <li>Job #125 - Failed (brokenlink.net)</li>
          </ul>
          <button>View All Jobs</button>
        </div>

        <div className="widget">
          <h3>Link Profile Summary</h3>
          <p>Key metrics for your monitored link profiles.</p>
          {/* Placeholder for link profile stats */}
          <p>Total Backlinks: <strong>1,234,567</strong></p>
          <p>Unique Referring Domains: <strong>12,345</strong></p>
          <p>New Backlinks (last 24h): <strong>+500</strong></p>
          <button>View Link Profiles</button>
        </div>

        <div className="widget">
          <h3>Usage & Quota</h3>
          <p>Monitor your API usage and remaining quotas.</p>
          {/* Placeholder for usage stats */}
          <p>API Calls This Month: <strong>15,000 / 20,000</strong></p>
          <p>Crawl Credits Used: <strong>500 / 1,000</strong></p>
          <button>Manage Subscription</button>
        </div>
      </div>

      <p className="dashboard-footer">
        Need assistance? Visit our <a href="/support">Support Center</a>.
      </p>
    </div>
  );
};

export default Dashboard;
