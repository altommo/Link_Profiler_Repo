import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { User } from '../types'; // Import User type

const Dashboard: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-nasa-cyan"> {/* Changed text color */}
          Welcome back, {user?.username || 'Guest'}!
        </h1>
        <p className="text-nasa-light-gray mt-2"> {/* Changed text color */}
          Here's an overview of your link profiling activities.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Recent Jobs Widget */}
        <div className="bg-nasa-gray rounded-lg shadow p-6 border border-nasa-cyan"> {/* Changed background and added border */}
          <h3 className="text-lg font-semibold text-nasa-cyan mb-4"> {/* Changed text color */}
            Recent Crawl Jobs
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-700"> {/* Changed border color */}
              <span className="text-sm text-nasa-light-gray">example.com</span> {/* Changed text color */}
              <span className="text-xs bg-green-500 text-white px-2 py-1 rounded"> {/* Changed bg/text color */}
                Completed
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-700"> {/* Changed border color */}
              <span className="text-sm text-nasa-light-gray">testsite.org</span> {/* Changed text color */}
              <span className="text-xs bg-nasa-amber text-nasa-dark-blue px-2 py-1 rounded"> {/* Changed bg/text color */}
                In Progress
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm text-nasa-light-gray">sample.net</span> {/* Changed text color */}
              <span className="text-xs bg-red-500 text-white px-2 py-1 rounded"> {/* Changed bg/text color */}
                Failed
              </span>
            </div>
          </div>
          <button className="w-full mt-4 text-nasa-cyan hover:text-nasa-blue text-sm font-medium"> {/* Changed text color */}
            View All Jobs →
          </button>
        </div>

        {/* Link Profile Summary */}
        <div className="bg-nasa-gray rounded-lg shadow p-6 border border-nasa-cyan"> {/* Changed background and added border */}
          <h3 className="text-lg font-semibold text-nasa-cyan mb-4"> {/* Changed text color */}
            Link Profile Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-nasa-light-gray">Total Backlinks:</span> {/* Changed text color */}
              <span className="font-semibold text-nasa-cyan">1,234,567</span> {/* Changed text color */}
            </div>
            <div className="flex justify-between">
              <span className="text-nasa-light-gray">Referring Domains:</span> {/* Changed text color */}
              <span className="font-semibold text-nasa-cyan">12,345</span> {/* Changed text color */}
            </div>
            <div className="flex justify-between">
              <span className="text-nasa-light-gray">New (24h):</span> {/* Changed text color */}
              <span className="font-semibold text-green-500">+500</span> {/* Changed text color */}
            </div>
          </div>
          <button className="w-full mt-4 text-nasa-cyan hover:text-nasa-blue text-sm font-medium"> {/* Changed text color */}
            View Profiles →
          </button>
        </div>

        {/* Usage & Quota */}
        <div className="bg-nasa-gray rounded-lg shadow p-6 border border-nasa-cyan"> {/* Changed background and added border */}
          <h3 className="text-lg font-semibold text-nasa-cyan mb-4"> {/* Changed text color */}
            Usage & Quota
          </h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-nasa-light-gray">API Calls</span> {/* Changed text color */}
                <span className="text-nasa-cyan">15,000 / 20,000</span> {/* Changed text color */}
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2"> {/* Changed background */}
                <div className="bg-nasa-blue h-2 rounded-full" style={{ width: '75%' }}></div> {/* Changed background */}
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-nasa-light-gray">Crawl Credits</span> {/* Changed text color */}
                <span className="text-nasa-cyan">500 / 1,000</span> {/* Changed text color */}
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2"> {/* Changed background */}
                <div className="bg-green-500 h-2 rounded-full" style={{ width: '50%' }}></div> {/* Changed background */}
              </div>
            </div>
          </div>
          <button className="w-full mt-4 text-nasa-cyan hover:text-nasa-blue text-sm font-medium"> {/* Changed text color */}
            Manage Subscription →
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-8 bg-nasa-gray rounded-lg shadow p-6 border border-nasa-cyan"> {/* Changed background and added border */}
        <h3 className="text-lg font-semibold text-nasa-cyan mb-4"> {/* Changed text color */}
          Quick Actions
        </h3>
        <div className="flex gap-4">
          <button className="btn-primary"> {/* Used custom button class */}
            Start New Crawl
          </button>
          <button className="btn-secondary"> {/* Used custom button class */}
            View Reports
          </button>
          <button className="btn-secondary"> {/* Used custom button class */}
            API Documentation
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
