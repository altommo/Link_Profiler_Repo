import React from 'react';
import { useAuth } from '../hooks/useAuth';

interface User {
  username: string;
  email: string;
}

const Dashboard: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Welcome back, {user?.username || 'Guest'}!
        </h1>
        <p className="text-gray-600 mt-2">
          Here's an overview of your link profiling activities.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Recent Jobs Widget */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Crawl Jobs
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b">
              <span className="text-sm text-gray-600">example.com</span>
              <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                Completed
              </span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <span className="text-sm text-gray-600">testsite.org</span>
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                In Progress
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm text-gray-600">sample.net</span>
              <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded">
                Failed
              </span>
            </div>
          </div>
          <button className="w-full mt-4 text-blue-600 hover:text-blue-800 text-sm font-medium">
            View All Jobs →
          </button>
        </div>

        {/* Link Profile Summary */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Link Profile Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Backlinks:</span>
              <span className="font-semibold">1,234,567</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Referring Domains:</span>
              <span className="font-semibold">12,345</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">New (24h):</span>
              <span className="font-semibold text-green-600">+500</span>
            </div>
          </div>
          <button className="w-full mt-4 text-blue-600 hover:text-blue-800 text-sm font-medium">
            View Profiles →
          </button>
        </div>

        {/* Usage & Quota */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Usage & Quota
          </h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">API Calls</span>
                <span>15,000 / 20,000</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full" style={{ width: '75%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Crawl Credits</span>
                <span>500 / 1,000</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div className="bg-green-600 h-2 rounded-full" style={{ width: '50%' }}></div>
              </div>
            </div>
          </div>
          <button className="w-full mt-4 text-blue-600 hover:text-blue-800 text-sm font-medium">
            Manage Subscription →
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-8 bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Quick Actions
        </h3>
        <div className="flex gap-4">
          <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium">
            Start New Crawl
          </button>
          <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md font-medium">
            View Reports
          </button>
          <button className="border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md font-medium">
            API Documentation
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;