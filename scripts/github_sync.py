#!/usr/bin/env python3
"""
AIEC Agent Hub - GitHub 日志同步工具 (改进版)
支持在 Claude 环境中运行
"""

import requests
import base64
import os
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, List

# ============ 配置 ============
REPO = "AIEC-Team/AIEC-agent-hub"
API_BASE = "https://api.github.com"
BRANCH = "main"

DEFAULT_MEMBER_ID = "kkkaka-oss"
DEFAULT_MEMBER_NAME = "Jiahe Gong"
DEFAULT_TEAM = "china"

TEAM_DIRS = {
    "china": "中国团队 china-team",
    "middle_east": "中东团队 middle-east",
    "best_allies": "最佳外援 best-allies"
}

WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ============ Token 管理 ============
_token = None

def set_token(token: str):
    """设置 GitHub token（供 Claude 调用）"""
    global _token
    _token = token

def get_token() -> str:
    """获取 token，优先级：set_token() > 环境变量"""
    if _token:
        return _token
    
    # 尝试多个环境变量名
    for var in ["GITHUB_PAT_TEAM_HUB", "GITHUB_TOKEN", "GH_TOKEN"]:
        token = os.environ.get(var)
        if token:
            return token
    
    raise EnvironmentError(
        "❌ 未找到 GitHub Token\n"
        "请通过以下方式之一设置：\n"
        "1. 调用 set_token('ghp_xxx')\n"
        "2. 设置环境变量 GITHUB_PAT_TEAM_HUB"
    )

def get_headers() -> Dict[str, str]:
    """获取认证头"""
    return {
        "Authorization": f"token {get_token()}",
        "Accept": "application/vnd.github.v3+json"
    }

# ============ 路径处理 ============
def encode_path(path: str) -> str:
    """对路径进行 URL 编码，处理中文"""
    # GitHub API 需要对路径中的特殊字符编码，但不编码斜杠
    parts = path.split("/")
    encoded_parts = [urllib.parse.quote(p, safe='') for p in parts]
    return "/".join(encoded_parts)

def get_file_path(member_id: str, team: str, date: str) -> str:
    """生成文件路径"""
    team_dir = TEAM_DIRS.get(team)
    if not team_dir:
        raise ValueError(f"❌ 无效团队: {team}，可选: {list(TEAM_DIRS.keys())}")
    return f"成员日志 members/{team_dir}/{member_id}/{date}_log.md"

# ============ 日志生成 ============
def create_log_content(
    member_id: str,
    member_name: str,
    team: str,
    date: str,
    content: str,
    structured_data: dict = None
) -> str:
    """
    生成带 Front Matter 的完整日志（A2A 友好格式）
    
    Args:
        content: 人类可读的日志正文
        structured_data: 可选的结构化数据，供 Agent 解析
            示例: {
                "done": [{"content": "完成任务1", "project": "proj-a"}],
                "in_progress": [{"content": "进行中", "blockers": ["等待审批"]}],
                "tomorrow": [{"content": "明天做"}],
                "ai_learning": {"topic": "xxx", "insight": "xxx"}
            }
    """
    synced_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday_en = WEEKDAYS_EN[dt.weekday()]
        date_formatted = dt.strftime("%Y.%m.%d")
    except ValueError:
        weekday_en = ""
        date_formatted = date
    
    # 构建 YAML front matter
    yaml_lines = [
        "---",
        f"member_id: {member_id}",
        f"member_name: {member_name}",
        f"date: {date}",
        f"synced_at: {synced_at}",
        f"team: {team}",
        "source: claude-skill",
    ]
    
    # 如果有结构化数据，加入 front matter
    if structured_data:
        yaml_lines.append("")
        yaml_lines.append("# === A2A Structured Data ===")
        
        if "done" in structured_data and structured_data["done"]:
            yaml_lines.append("tasks_done:")
            for task in structured_data["done"]:
                yaml_lines.append(f"  - content: \"{task.get('content', '')}\"")
                if task.get("project"):
                    yaml_lines.append(f"    project: {task['project']}")
        
        if "in_progress" in structured_data and structured_data["in_progress"]:
            yaml_lines.append("tasks_in_progress:")
            for task in structured_data["in_progress"]:
                yaml_lines.append(f"  - content: \"{task.get('content', '')}\"")
                if task.get("blockers"):
                    yaml_lines.append(f"    blockers: {task['blockers']}")
        
        if "tomorrow" in structured_data and structured_data["tomorrow"]:
            yaml_lines.append("tasks_tomorrow:")
            for task in structured_data["tomorrow"]:
                yaml_lines.append(f"  - content: \"{task.get('content', '')}\"")
        
        if "ai_learning" in structured_data and structured_data["ai_learning"]:
            al = structured_data["ai_learning"]
            yaml_lines.append("ai_learning:")
            if al.get("topic"):
                yaml_lines.append(f"  topic: \"{al['topic']}\"")
            if al.get("insight"):
                yaml_lines.append(f"  insight: \"{al['insight']}\"")
            if al.get("applied_to"):
                yaml_lines.append(f"  applied_to: \"{al['applied_to']}\"")
        
        # 汇总 blockers（方便其他 Agent 快速查询）
        all_blockers = []
        for task in structured_data.get("in_progress", []):
            all_blockers.extend(task.get("blockers", []))
        if all_blockers:
            yaml_lines.append(f"blockers: {all_blockers}")
        else:
            yaml_lines.append("blockers: []")
    
    yaml_lines.append("---")
    
    front_matter = "\n".join(yaml_lines)
    
    return f"""{front_matter}

# {member_name} | {date_formatted} {weekday_en}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_synced at {datetime.now().strftime("%H:%M")}_
"""

# ============ Push 日志 ============
def push_log(
    content: str,
    member_id: str = DEFAULT_MEMBER_ID,
    member_name: str = DEFAULT_MEMBER_NAME,
    team: str = DEFAULT_TEAM,
    date: str = None,
    token: str = None,
    structured_data: dict = None
) -> Dict:
    """
    推送日志到 GitHub
    
    Args:
        content: 日志正文（不含 front matter 和标题）
        member_id: 成员 ID
        member_name: 成员姓名  
        team: 团队
        date: 日期，默认今天
        token: GitHub token（可选，不传则用环境变量）
        structured_data: A2A 结构化数据（可选）
            示例: {
                "done": [{"content": "完成xxx", "project": "proj"}],
                "in_progress": [{"content": "进行中", "blockers": ["等xx"]}],
                "tomorrow": [{"content": "明天做"}],
                "ai_learning": {"topic": "xxx", "insight": "xxx"}
            }
    
    Returns:
        {"success": True, "url": "..."} 或 {"success": False, "error": "..."}
    """
    if token:
        set_token(token)
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    path = get_file_path(member_id, team, date)
    encoded_path = encode_path(path)
    url = f"{API_BASE}/repos/{REPO}/contents/{encoded_path}"
    
    headers = get_headers()
    
    # 检查文件是否存在
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json()["sha"]
            print(f"📝 更新已有日志: {date}")
        elif r.status_code == 404:
            print(f"📝 创建新日志: {date}")
        elif r.status_code == 401:
            return {"success": False, "error": "Token 无效或已过期"}
        elif r.status_code == 403:
            return {"success": False, "error": "Token 权限不足，需要 repo 权限"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"网络错误: {e}"}
    
    # 生成完整内容
    full_content = create_log_content(member_id, member_name, team, date, content, structured_data)
    
    # 构建请求
    data = {
        "message": f"📝 [{member_id}] Sync daily log for {date}",
        "content": base64.b64encode(full_content.encode("utf-8")).decode("utf-8"),
        "branch": BRANCH
    }
    if sha:
        data["sha"] = sha
    
    # 推送
    try:
        response = requests.put(url, headers=headers, json=data, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            file_url = result['content']['html_url']
            print(f"✅ 推送成功!")
            print(f"🔗 查看: {file_url}")
            return {"success": True, "url": file_url}
        else:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json().get("message", response.text[:200])
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text[:200]}"
            print(f"❌ 推送失败: {error_msg}")
            return {"success": False, "error": error_msg}
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"网络错误: {e}"}

# ============ Pull 日志 ============
def pull_log(
    member_id: str,
    team: str = DEFAULT_TEAM,
    date: str = None,
    token: str = None
) -> Optional[str]:
    """拉取指定日志"""
    if token:
        set_token(token)
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    path = get_file_path(member_id, team, date)
    encoded_path = encode_path(path)
    url = f"{API_BASE}/repos/{REPO}/contents/{encoded_path}"
    
    try:
        r = requests.get(url, headers=get_headers(), timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            return content
    except:
        pass
    return None

# ============ 团队日志 ============
def pull_team_daily_logs(
    team: str = DEFAULT_TEAM, 
    date: str = None,
    token: str = None
) -> Dict[str, str]:
    """拉取团队所有人的日志"""
    if token:
        set_token(token)
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    team_dir = TEAM_DIRS.get(team, TEAM_DIRS["china"])
    path = f"成员日志 members/{team_dir}"
    encoded_path = encode_path(path)
    url = f"{API_BASE}/repos/{REPO}/contents/{encoded_path}"
    
    logs = {}
    
    try:
        r = requests.get(url, headers=get_headers(), timeout=10)
        if r.status_code != 200:
            return logs
        
        members = [item["name"] for item in r.json() if item["type"] == "dir"]
        
        for member_id in members:
            content = pull_log(member_id, team, date)
            if content:
                logs[member_id] = content
        
        print(f"📊 获取 {len(logs)}/{len(members)} 位成员的日志")
    except:
        pass
    
    return logs

# ============ 测试连接 ============
def test_connection(token: str = None) -> Dict:
    """测试 GitHub 连接和权限"""
    if token:
        set_token(token)
    
    try:
        headers = get_headers()
        
        # 测试 token 有效性
        r = requests.get(f"{API_BASE}/user", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"success": False, "error": f"Token 无效: HTTP {r.status_code}"}
        
        user = r.json().get("login", "unknown")
        
        # 测试仓库访问
        r = requests.get(f"{API_BASE}/repos/{REPO}", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"success": False, "error": f"无法访问仓库 {REPO}"}
        
        return {
            "success": True, 
            "user": user,
            "repo": REPO,
            "message": f"✅ 连接成功！用户: {user}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ 团队日报搜索功能（新增） ============
def parse_front_matter(content: str) -> Dict:
    """
    解析日报的 YAML Front Matter
    
    Args:
        content: 日报完整内容
    
    Returns:
        解析后的字典，如果解析失败返回空字典
    """
    try:
        if not content.startswith("---"):
            return {}
        
        # 提取 front matter 部分
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        
        front_matter = parts[1].strip()
        
        # 简单解析（不依赖 yaml 库）
        data = {}
        current_key = None
        current_list = None
        
        for line in front_matter.split('\n'):
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            
            # 顶级键值对
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if value:
                    data[key] = value.strip('"\'')
                else:
                    current_key = key
                    current_list = []
                    data[key] = current_list
            
            # 列表项
            elif line.startswith('  - ') and current_list is not None:
                item = line[4:].strip()
                current_list.append(item)
        
        return data
    except:
        return {}


def search_team_logs(
    keyword: str = None,
    project: str = None,
    member: str = None,
    team: str = DEFAULT_TEAM,
    date_from: str = None,
    date_to: str = None,
    limit: int = 10
) -> List[Dict]:
    """
    搜索团队日报
    
    Args:
        keyword: 搜索关键词（在正文和 Front Matter 中搜索）
        project: 项目名称
        member: 成员 ID
        team: 团队名称
        date_from: 起始日期 (YYYY-MM-DD)
        date_to: 结束日期 (YYYY-MM-DD)
        limit: 返回结果数量限制
    
    Returns:
        匹配的日志列表，每项包含：
        {
            "member_id": "...",
            "member_name": "...",
            "date": "...",
            "match_type": "keyword/project/...",
            "excerpt": "...",  # 匹配片段
            "url": "...",
            "front_matter": {...}
        }
    
    Examples:
        search_team_logs(keyword="Prompt 优化")
        search_team_logs(project="ai-tutor")
        search_team_logs(member="Bryce")
    """
    results = []
    
    team_dir = TEAM_DIRS.get(team, TEAM_DIRS["china"])
    members_path = f"成员日志 members/{team_dir}"
    encoded_path = encode_path(members_path)
    url = f"{API_BASE}/repos/{REPO}/contents/{encoded_path}"
    
    try:
        headers = get_headers()
        
        # 获取团队成员列表
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return results
        
        members = [item["name"] for item in r.json() if item["type"] == "dir"]
        
        # 如果指定了成员，只搜索该成员
        if member:
            members = [m for m in members if member.lower() in m.lower()]
        
        # 遍历每个成员的日志
        for member_id in members:
            member_path = f"{members_path}/{member_id}"
            encoded_member_path = encode_path(member_path)
            member_url = f"{API_BASE}/repos/{REPO}/contents/{encoded_member_path}"
            
            r = requests.get(member_url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            
            files = r.json()
            
            # 按日期排序（最新的在前）
            log_files = [f for f in files if f["name"].endswith("_log.md")]
            log_files.sort(key=lambda x: x["name"], reverse=True)
            
            # 遍历日志文件
            for log_file in log_files[:20]:  # 每个成员最多检查最近20个日志
                file_date = log_file["name"].replace("_log.md", "")
                
                # 日期过滤
                if date_from and file_date < date_from:
                    continue
                if date_to and file_date > date_to:
                    continue
                
                # 获取文件内容
                try:
                    content_r = requests.get(log_file["download_url"], timeout=10)
                    if content_r.status_code != 200:
                        continue
                    
                    content = content_r.text
                    
                    # 解析 Front Matter
                    front_matter = parse_front_matter(content)
                    
                    # 检查是否匹配
                    match = False
                    match_type = ""
                    excerpt = ""
                    
                    # 项目匹配
                    if project:
                        if any(project.lower() in str(v).lower() for v in front_matter.values()):
                            match = True
                            match_type = "project"
                            excerpt = f"项目: {project}"
                    
                    # 关键词匹配
                    if keyword:
                        keyword_lower = keyword.lower()
                        if keyword_lower in content.lower():
                            match = True
                            match_type = "keyword"
                            
                            # 提取匹配片段
                            content_lines = content.split('\n')
                            for i, line in enumerate(content_lines):
                                if keyword_lower in line.lower():
                                    # 提取前后各2行作为上下文
                                    start = max(0, i-2)
                                    end = min(len(content_lines), i+3)
                                    excerpt = '\n'.join(content_lines[start:end])
                                    break
                    
                    # 如果没有指定任何过滤条件，返回所有
                    if not keyword and not project:
                        match = True
                        match_type = "all"
                        # 提取 AI 学习部分作为摘要
                        ai_learning = front_matter.get("ai_learning", "")
                        if ai_learning:
                            excerpt = f"AI 学习: {ai_learning}"
                    
                    if match:
                        results.append({
                            "member_id": member_id,
                            "member_name": front_matter.get("member_name", member_id),
                            "date": file_date,
                            "match_type": match_type,
                            "excerpt": excerpt[:300],  # 限制长度
                            "url": log_file["html_url"],
                            "front_matter": front_matter
                        })
                        
                        if len(results) >= limit:
                            return results
                
                except Exception as e:
                    continue
        
        return results
    
    except Exception as e:
        print(f"搜索出错: {e}")
        return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
每日日志同步工具

用法:
  python github_sync.py test              # 测试连接
  python github_sync.py push "日志内容"    # 推送日志
  python github_sync.py pull [member_id]  # 拉取日志
  python github_sync.py team [date]       # 团队日志
        """)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "test":
        result = test_connection()
        print(result.get("message") or result.get("error"))
    
    elif cmd == "push" and len(sys.argv) >= 3:
        content = sys.argv[2].replace("\\n", "\n")
        push_log(content)
    
    elif cmd == "pull":
        member_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MEMBER_ID
        content = pull_log(member_id)
        if content:
            print(content)
        else:
            print("未找到日志")
    
    elif cmd == "team":
        date = sys.argv[2] if len(sys.argv) > 2 else None
        logs = pull_team_daily_logs(date=date)
        for member, content in logs.items():
            print(f"\n{'='*50}\n👤 {member}\n{'='*50}")
            print(content[:500] + "..." if len(content) > 500 else content)
