#!/usr/bin/env tsx
/**
 * Parallel Agent Executor
 *
 * GitHub Actionsワークフローから呼び出され、Issueを分析してコードを生成します。
 *
 * Usage:
 *   npm run agents:parallel:exec -- --issue 2 --concurrency 3 --log-level info
 */

import Anthropic from '@anthropic-ai/sdk';

interface AgentOptions {
  issue: number;
  concurrency: number;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
}

interface IssueData {
  number: number;
  title: string;
  body: string;
  labels: string[];
}

interface TaskResult {
  agent: string;
  status: 'success' | 'failure';
  output?: string;
  error?: string;
}

// ログ出力
function log(level: string, message: string, ...args: unknown[]) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level.toUpperCase()}] ${message}`, ...args);
}

// GitHub Issue取得
async function fetchIssue(issueNumber: number): Promise<IssueData> {
  const repo = process.env.REPOSITORY || 'PLark-droid/Robo-Pat-Create';
  const token = process.env.GITHUB_TOKEN;

  const url = `https://api.github.com/repos/${repo}/issues/${issueNumber}`;
  const headers: Record<string, string> = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Robo-Pat-Agent'
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, { headers });

  if (!response.ok) {
    throw new Error(`Failed to fetch issue: ${response.status} ${response.statusText}`);
  }

  const data = await response.json() as {
    number: number;
    title: string;
    body: string | null;
    labels?: Array<{ name: string }>;
  };

  return {
    number: data.number,
    title: data.title,
    body: data.body || '',
    labels: data.labels?.map((l) => l.name) || []
  };
}

// Issueを分析してタスクを抽出
async function analyzeIssue(issue: IssueData, client: Anthropic): Promise<string[]> {
  log('info', `Analyzing issue #${issue.number}: ${issue.title}`);

  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 2048,
    system: `あなたはソフトウェア開発タスクのアナリストです。
GitHubのIssueを分析し、実装すべき具体的なタスクをリストアップしてください。

出力形式（JSON配列）:
["タスク1", "タスク2", "タスク3"]

タスクは具体的で実行可能な粒度にしてください。`,
    messages: [{
      role: 'user',
      content: `# Issue #${issue.number}: ${issue.title}

${issue.body}

ラベル: ${issue.labels.join(', ')}`
    }]
  });

  const text = response.content[0].type === 'text' ? response.content[0].text : '';

  // JSONを抽出
  const match = text.match(/\[[\s\S]*\]/);
  if (match) {
    try {
      return JSON.parse(match[0]);
    } catch {
      log('warn', 'Failed to parse tasks JSON, using raw text');
    }
  }

  return [text];
}

// コード生成エージェント
async function codeGenAgent(task: string, context: IssueData, client: Anthropic): Promise<TaskResult> {
  log('info', `CodeGenAgent: Processing task - ${task}`);

  try {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      system: `あなたはRobo-Pat AI プロジェクトのコード生成エージェントです。
このプロジェクトは自然言語からRPAスクリプトを生成するツールです。

技術スタック:
- CLI: TypeScript + Node.js
- RPA生成: Python
- AI: Anthropic Claude API

コード生成時の注意:
- 既存のコードスタイルに従う
- 適切なエラーハンドリング
- 型安全性を重視`,
      messages: [{
        role: 'user',
        content: `Issue #${context.number}: ${context.title}

タスク: ${task}

必要なコードを生成してください。ファイルパスとコード内容を明示してください。`
      }]
    });

    const output = response.content[0].type === 'text' ? response.content[0].text : '';

    return {
      agent: 'CodeGenAgent',
      status: 'success',
      output
    };
  } catch (error) {
    return {
      agent: 'CodeGenAgent',
      status: 'failure',
      error: String(error)
    };
  }
}

// メイン実行
async function main() {
  // 引数パース
  const args = process.argv.slice(2);
  const options: AgentOptions = {
    issue: 0,
    concurrency: 3,
    logLevel: 'info'
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--issue':
        options.issue = parseInt(args[++i], 10);
        break;
      case '--concurrency':
        options.concurrency = parseInt(args[++i], 10);
        break;
      case '--log-level':
        options.logLevel = args[++i] as AgentOptions['logLevel'];
        break;
    }
  }

  if (!options.issue) {
    console.error('Error: --issue is required');
    process.exit(1);
  }

  log('info', '🚀 Parallel Agent Executor starting...');
  log('info', `Issue: #${options.issue}, Concurrency: ${options.concurrency}`);

  // Anthropic クライアント初期化
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    log('error', 'ANTHROPIC_API_KEY is not set');
    process.exit(1);
  }

  const client = new Anthropic({ apiKey });

  try {
    // Issue取得
    const issue = await fetchIssue(options.issue);
    log('info', `Fetched issue: ${issue.title}`);

    // タスク分析
    const tasks = await analyzeIssue(issue, client);
    log('info', `Identified ${tasks.length} tasks`);

    // 並列実行（concurrencyで制限）
    const results: TaskResult[] = [];

    for (let i = 0; i < tasks.length; i += options.concurrency) {
      const batch = tasks.slice(i, i + options.concurrency);
      const batchResults = await Promise.all(
        batch.map(task => codeGenAgent(task, issue, client))
      );
      results.push(...batchResults);
    }

    // 結果サマリー
    const successful = results.filter(r => r.status === 'success').length;
    const failed = results.filter(r => r.status === 'failure').length;

    log('info', `✅ Completed: ${successful} success, ${failed} failed`);

    // 結果を出力
    for (const result of results) {
      if (result.status === 'success' && result.output) {
        console.log('\n' + '='.repeat(60));
        console.log(`Agent: ${result.agent}`);
        console.log('='.repeat(60));
        console.log(result.output);
      }
    }

    if (failed > 0) {
      process.exit(1);
    }

  } catch (error) {
    log('error', 'Agent execution failed:', error);
    process.exit(1);
  }
}

main();
