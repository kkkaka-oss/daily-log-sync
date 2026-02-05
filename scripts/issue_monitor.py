#!/usr/bin/env python3
"""
GitHub Issue 监听与自动回复工具

功能：
1. 检查是否有新的 Issue 提问（针对 kkkaka-oss）
2. 检查是否有新的评论回复
3. 自动生成回复并发送
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# ============ 配置 ============
REPO = "AIEC-Team/AIEC-agent-hub"
API_BASE = "https://api.github.com"
MEMBER_ID = "kkkaka-oss"
MEMBER_NAME = "贡嘉荷"

# 状态文件，记录已处理的 Issue/评论
STATE_FILE = os.path.join(os.path.dirname(__file__), ".issue_state.json")

# ============ Token 管理 ============
def get_token() -> str:
    for var in ["GITHUB_PAT_TEAM_HUB", "GITHUB_TOKEN", "GH_TOKEN"]:
        token = os.environ.get(var)
        if token:
            return token
    raise EnvironmentError("❌ 未找到 GitHub Token")

def get_headers() -> Dict[str, str]:
    return {
        "Authorization": f"token {get_token()}",
        "Accept": "application/vnd.github.v3+json"
    }

# ============ 状态管理 ============
def load_state() -> Dict:
    """加载已处理的状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"replied_issues": [], "replied_comments": [], "last_check": None}

def save_state(state: Dict):
    """保存状态"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ============ Issue 检查 ============
def get_issues_for_member(member_id: str = MEMBER_ID) -> List[Dict]:
    """获取针对指定成员的 Issues"""
    headers = get_headers()
    
    # 搜索标题或内容中包含成员 ID 的 Issues
    url = f"{API_BASE}/repos/{REPO}/issues?state=open&per_page=50"
    r = requests.get(url, headers=headers, timeout=10)
    
    if r.status_code != 200:
        print(f"❌ 获取 Issues 失败: {r.status_code}")
        return []
    
    issues = r.json()
    member_issues = []
    
    for issue in issues:
        title = issue.get('title', '')
        body = issue.get('body', '') or ''
        
        # 检查是否是给这个成员的问题
        if member_id.lower() in title.lower() or f"@{member_id}" in body:
            member_issues.append(issue)
    
    return member_issues

def get_issue_comments(issue_number: int) -> List[Dict]:
    """获取 Issue 的所有评论"""
    headers = get_headers()
    url = f"{API_BASE}/repos/{REPO}/issues/{issue_number}/comments"
    r = requests.get(url, headers=headers, timeout=10)
    
    if r.status_code == 200:
        return r.json()
    return []

def check_new_questions() -> List[Dict]:
    """检查是否有新的问题需要回复"""
    state = load_state()
    replied_issues = set(state.get("replied_issues", []))
    
    issues = get_issues_for_member()
    new_questions = []
    
    for issue in issues:
        issue_num = issue['number']
        
        # 检查是否已经回复过
        if issue_num in replied_issues:
            continue
        
        # 检查评论中是否已经有 kkkaka-oss 的回复
        comments = get_issue_comments(issue_num)
        has_my_reply = any(
            c['user']['login'] == MEMBER_ID for c in comments
        )
        
        if not has_my_reply:
            new_questions.append({
                "issue_number": issue_num,
                "title": issue['title'],
                "body": issue.get('body', ''),
                "author": issue['user']['login'],
                "url": issue['html_url'],
                "created_at": issue['created_at']
            })
    
    return new_questions

def check_new_replies() -> List[Dict]:
    """检查是否有新的回复（别人回复了我的评论）"""
    state = load_state()
    replied_comments = set(state.get("replied_comments", []))
    
    issues = get_issues_for_member()
    new_replies = []
    
    for issue in issues:
        comments = get_issue_comments(issue['number'])
        
        my_comment_times = []
        for c in comments:
            if c['user']['login'] == MEMBER_ID:
                my_comment_times.append(c['created_at'])
        
        if not my_comment_times:
            continue
        
        # 找出在我最后一次评论之后的其他人的评论
        last_my_comment = max(my_comment_times)
        
        for c in comments:
            if c['user']['login'] != MEMBER_ID and c['created_at'] > last_my_comment:
                if c['id'] not in replied_comments:
                    new_replies.append({
                        "issue_number": issue['number'],
                        "issue_title": issue['title'],
                        "comment_id": c['id'],
                        "author": c['user']['login'],
                        "body": c['body'],
                        "url": c['html_url'],
                        "created_at": c['created_at']
                    })
    
    return new_replies

# ============ 回复功能 ============
def post_comment(issue_number: int, body: str) -> Dict:
    """发送评论到 Issue"""
    headers = get_headers()
    url = f"{API_BASE}/repos/{REPO}/issues/{issue_number}/comments"
    
    r = requests.post(url, headers=headers, json={"body": body}, timeout=30)
    
    if r.status_code == 201:
        result = r.json()
        print(f"✅ 回复成功！")
        print(f"🔗 查看: {result['html_url']}")
        return {"success": True, "url": result['html_url']}
    else:
        print(f"❌ 回复失败: {r.status_code}")
        print(r.text)
        return {"success": False, "error": r.text}

def mark_issue_replied(issue_number: int):
    """标记 Issue 已回复"""
    state = load_state()
    if issue_number not in state["replied_issues"]:
        state["replied_issues"].append(issue_number)
    state["last_check"] = datetime.now().isoformat()
    save_state(state)

def mark_comment_replied(comment_id: int):
    """标记评论已处理"""
    state = load_state()
    if comment_id not in state["replied_comments"]:
        state["replied_comments"].append(comment_id)
    state["last_check"] = datetime.now().isoformat()
    save_state(state)

# ============ 主要功能 ============
def check_and_report() -> Dict:
    """
    检查新问题和新回复，返回需要处理的内容
    
    Returns:
        {
            "new_questions": [...],  # 新的问题
            "new_replies": [...],    # 新的回复
        }
    """
    print("=" * 60)
    print(f"🔍 检查 GitHub Issues (成员: {MEMBER_ID})")
    print("=" * 60)
    
    new_questions = check_new_questions()
    new_replies = check_new_replies()
    
    if new_questions:
        print(f"\n📬 发现 {len(new_questions)} 个新问题:")
        for q in new_questions:
            print(f"\n  Issue #{q['issue_number']}: {q['title']}")
            print(f"  提问者: {q['author']}")
            print(f"  链接: {q['url']}")
            print(f"  内容预览: {q['body'][:200]}..." if len(q['body']) > 200 else f"  内容: {q['body']}")
    else:
        print("\n✅ 没有新问题")
    
    if new_replies:
        print(f"\n💬 发现 {len(new_replies)} 条新回复:")
        for r in new_replies:
            print(f"\n  Issue #{r['issue_number']}: {r['issue_title']}")
            print(f"  回复者: {r['author']}")
            print(f"  内容预览: {r['body'][:200]}..." if len(r['body']) > 200 else f"  内容: {r['body']}")
    else:
        print("\n✅ 没有新回复")
    
    return {
        "new_questions": new_questions,
        "new_replies": new_replies
    }

def reply_to_issue(issue_number: int, reply_content: str) -> Dict:
    """
    回复指定的 Issue
    
    Args:
        issue_number: Issue 编号
        reply_content: 回复内容
    
    Returns:
        {"success": True/False, "url": "..."}
    """
    result = post_comment(issue_number, reply_content)
    if result.get("success"):
        mark_issue_replied(issue_number)
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
GitHub Issue 监听工具

用法:
  python issue_monitor.py check              # 检查新问题和回复
  python issue_monitor.py reply <issue_num> "回复内容"  # 回复指定 Issue
        """)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "check":
        check_and_report()
    
    elif cmd == "reply" and len(sys.argv) >= 4:
        issue_num = int(sys.argv[2])
        content = sys.argv[3]
        reply_to_issue(issue_num, content)
    
    else:
        print("❌ 未知命令")

