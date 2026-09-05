// Development-only catalog access. Never import this file into the application.
const [tool = 'search', input = '{"query":"expandable tabs","type":"component","limit":3}'] = process.argv.slice(2);
if (!['search', 'get_component', 'get_theme'].includes(tool)) throw new Error('Only catalog retrieval is supported.');
const key = process.env.TWENTY_FIRST_API_KEY;
if (!key) throw new Error('Set TWENTY_FIRST_API_KEY in the gitignored root .env.');
const response = await fetch('https://21st.dev/api/mcp', {
  method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', 'x-api-key': key },
  body: JSON.stringify({jsonrpc:'2.0', id:1, method:'tools/call', params:{name:tool, arguments:JSON.parse(input)}}),
});
if (!response.ok) throw new Error(`21st catalog returned HTTP ${response.status}`);
console.log(JSON.stringify(await response.json(), null, 2));
