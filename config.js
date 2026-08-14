window.PTO_CONFIG = Object.freeze({
  version: '0.2.0',
  jobsFeed: './data/jobs.json',
  sourceStatusFeed: './data/source_status.json',
  interviewAssetsRepo: 'https://github.com/MLliu6/26-27-interview',
  // Optional. A production GitHub login needs a server-side token exchange.
  // Point this to your own OAuth callback/proxy when one is provisioned.
  githubOAuthProxy: '',
  githubClientId: '',
  githubOAuthScopes: 'read:user user:email',
});
