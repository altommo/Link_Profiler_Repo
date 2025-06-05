import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple
import tempfile # Added for tempfile in video analysis

class PlaceholderMigrator:
    """Automatically migrate placeholder code to real implementations."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "migration_backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def migrate_all_placeholders(self):
        """Run all placeholder migrations."""
        print("Starting placeholder migration...")
        
        migrations = [
            self.migrate_wayback_client,
            self.migrate_ai_service_video,
            self.migrate_environment_vars,
            self.migrate_session_managers,
            self.fix_redis_bug
        ]
        
        for migration in migrations:
            try:
                migration()
            except Exception as e:
                print(f"Error in migration {migration.__name__}: {e}")
        
        print("Placeholder migration completed!")
    
    def migrate_wayback_client(self):
        """Replace simulation methods in Wayback client."""
        client_path = self.project_root / "Link_Profiler/clients/wayback_machine_client.py"
        
        if not client_path.exists():
            print(f"Wayback client not found: {client_path}")
            return
        
        # Create backup
        self._backup_file(client_path)
        
        # Read current content
        with open(client_path, 'r') as f:
            content = f.read()
        
        # Remove simulation method
        content = re.sub(
            r'def _simulate_snapshots.*?return simulated_results',
            '# Simulation method removed - using real API implementation',
            content,
            flags=re.DOTALL
        )
        
        # Remove simulation fallback calls
        content = re.sub(
            r'return self\._simulate_snapshots\([^)]+\)',
            'return []  # Return empty list instead of simulation',
            content
        )
        
        # Write updated content
        with open(client_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Migrated Wayback client: {client_path}")
    
    def migrate_ai_service_video(self):
        """Replace simulated video analysis in AI service."""
        service_path = self.project_root / "Link_Profiler/services/ai_service.py"
        
        if not service_path.exists():
            print(f"AI service not found: {service_path}")
            return
        
        # Create backup
        self._backup_file(service_path)
        
        # Read current content
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Add deprecation warning to video analysis method
        video_method_replacement = '''
    async def analyze_video_content(self, video_url: str, video_data: Optional[bytes] = None, 
                                  max_frames: int = 10) -> Dict[str, Any]:
        """
        Real video content analysis using OpenAI Vision API.
        Extracts frames from video and analyzes them with GPT-4 Vision.
        
        Args:
            video_url: URL of the video
            video_data: Raw video bytes (optional)
            max_frames: Maximum number of frames to extract and analyze
            
        Returns:
            Dictionary with transcription, topics, and analysis
        """
        if not self.enabled or not self.openrouter_client:
            raise NotImplementedError("AI service is disabled. Video analysis requires AI integration.")
        
        # Download video if only URL provided
        if video_data is None and video_url:
            video_data = await self._download_video(video_url)
        
        if not video_data:
            raise ValueError("No video data available for analysis")
        
        # Extract frames from video
        frames = await self._extract_video_frames(video_data, max_frames)
        
        if not frames:
            raise ValueError("No frames could be extracted from video")
        
        # Analyze frames with Vision API
        analysis_results = []
        for i, frame in enumerate(frames):
            frame_analysis = await self._analyze_video_frame(frame, i)
            if frame_analysis:
                analysis_results.append(frame_analysis)
        
        # Synthesize results
        return await self._synthesize_video_analysis(analysis_results, video_url)
    
    async def _download_video(self, video_url: str) -> Optional[bytes]:
        """Download video from URL."""
        try:
            async with self.session_manager.get(video_url, timeout=60) as response:
                response.raise_for_status()
                return await response.read()
        except Exception as e:
            self.logger.error(f"Error downloading video from {video_url}: {e}")
            return None
    
    async def _extract_video_frames(self, video_data: bytes, max_frames: int) -> List[bytes]:
        """Extract frames from video using OpenCV."""
        frames = []
        
        # Save video data to temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(video_data)
            temp_path = temp_file.name
        
        try:
            # Open video with OpenCV
            cap = cv2.VideoCapture(temp_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames == 0:
                return frames
            
            # Calculate frame interval
            interval = max(1, total_frames // max_frames)
            
            frame_count = 0
            while len(frames) < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % interval == 0:
                    # Convert frame to JPEG bytes
                    _, buffer = cv2.imencode('.jpg', frame)
                    frames.append(buffer.tobytes())
                
                frame_count += 1
            
            cap.release()
            
        except Exception as e:
            self.logger.error(f"Error extracting video frames: {e}")
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
        
        return frames
    
    async def _analyze_video_frame(self, frame_data: bytes, frame_index: int) -> Optional[Dict[str, Any]]:
        """Analyze a single video frame with Vision API."""
        try:
            # Encode frame as base64
            frame_b64 = base64.b64encode(frame_data).decode('utf-8')
            
            prompt = f"""
            Analyze this video frame (frame #{frame_index}). Describe:
            1. What objects, people, or text you see
            2. Any actions or activities taking place
            3. The setting or environment
            4. Any text that appears on screen
            
            Provide response as JSON with keys: objects, actions, setting, text_content
            """
            
            # Make API call with image
            response = await self.openrouter_client.http_client.chat.completions.create(
                model=self.models.get("content_nlp_analysis", "anthropic/claude-3-haiku"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            import json
            return json.loads(content)
            
        except Exception as e:
            self.logger.error(f"Error analyzing video frame {frame_index}: {e}")
            return None
    
    async def _synthesize_video_analysis(self, frame_analyses: List[Dict[str, Any]], 
                                       video_url: str) -> Dict[str, Any]:
        """Synthesize individual frame analyses into comprehensive video analysis."""
        if not frame_analyses:
            return {
                "transcription": "",
                "topics": [],
                "timeline": [],
                "summary": "No analysis data available"
            }
        
        # Combine all text content found in frames
        all_text = []
        all_objects = []
        all_actions = []
        timeline = []
        
        for i, analysis in enumerate(frame_analyses):
            if analysis.get('text_content'):
                all_text.append(analysis['text_content'])
            if analysis.get('objects'):
                all_objects.extend(analysis['objects'])
            if analysis.get('actions'):
                all_actions.extend(analysis['actions'])
            
            # Build timeline
            timeline.append({
                "frame": i,
                "timestamp": f"{i*2}s",  # Approximate 2 seconds per frame
                "description": f"{analysis.get('setting', '')} - {analysis.get('actions', '')}"
            })
        
        # Extract unique topics
        topics = list(set(all_objects + all_actions))
        
        # Generate summary
        summary_prompt = f"""
        Based on the following video frame analyses, provide a comprehensive summary:
        
        Objects seen: {', '.join(set(all_objects))}
        Actions observed: {', '.join(set(all_actions))}
        Text found: {', '.join(all_text)}
        
        Provide a coherent summary of what this video appears to be about.
        """
        
        summary = await self._call_ai_with_cache(
            "content_generation", 
            summary_prompt, 
            f"video_summary:{hash(str(frame_analyses))}"
        )
        
        return {
            "transcription": ' '.join(all_text),
            "topics": topics[:10],  # Limit to top 10 topics
            "timeline": timeline,
            "summary": summary.get('summary', 'Video analysis completed') if summary else "Analysis completed",
            "objects_detected": list(set(all_objects)),
            "actions_detected": list(set(all_actions))
        }
'''
        
        # Replace the video analysis method
        content = re.sub(
            r'async def analyze_video_content.*?return \{[^}]+\}',
            video_method_replacement.strip(),
            content,
            flags=re.DOTALL
        )
        
        # Write updated content
        with open(service_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Migrated AI service video analysis: {service_path}")
    
    def migrate_environment_vars(self):
        """Migrate hardcoded values to environment variables."""
        config_path = self.project_root / "Link_Profiler/config/config.yaml"
        
        if not config_path.exists():
            print(f"Config file not found: {config_path}")
            return
        
        # Create backup
        self._backup_file(config_path)
        
        # Read current content
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Replace hardcoded credentials
        replacements = [
            (r'redis://:redis_secure_pass_456@127\.0\.0\.1:6379/0', '${LP_REDIS_URL:-redis://localhost:6379/0}'),
            (r'monitor_secure_password_123', '${LP_MONITOR_PASSWORD}'),
            (r'xKroXcaIePQydhdhS4GMhdMfTsjhKzthaoL5OmU5MBA', '${LP_AUTH_SECRET_KEY}'),
            (r'postgresql://postgres:postgres@localhost:5432/link_profiler_db', '${LP_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/link_profiler_db}'),
            (r'openrouter_api_key: ""', 'openrouter_api_key: "${LP_AI_OPENROUTER_API_KEY}"') # Update AI key
        ]
        
        for old_value, new_value in replacements:
            content = re.sub(old_value, new_value, content)
        
        # Write updated content
        with open(config_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Migrated hardcoded credentials: {config_path}")
    
    def migrate_session_managers(self):
        """Update client files to use centralized session manager."""
        clients_dir = self.project_root / "Link_Profiler/clients"
        
        if not clients_dir.exists():
            print(f"Clients directory not found: {clients_dir}")
            return
        
        # Find all client files
        client_files = list(clients_dir.glob("*.py"))
        
        for client_file in client_files:
            if client_file.name.startswith('__'):
                continue
            
            # Create backup
            self._backup_file(client_file)
            
            # Read content
            with open(client_file, 'r') as f:
                content = f.read()
            
            # Check if it has session management
            if '_session' in content and 'aiohttp.ClientSession' in content:
                # Add base client import
                if 'from Link_Profiler.clients.base_client import BaseAPIClient' not in content:
                    # Add import after other imports
                    import_section = re.search(r'(from Link_Profiler\..*?\n)+', content)
                    if import_section:
                        new_import = import_section.group(0) + 'from Link_Profiler.clients.base_client import BaseAPIClient\n'
                        content = content.replace(import_section.group(0), new_import)
                
                # Replace class inheritance
                content = re.sub(
                    r'class (\w+Client)(?:\([^)]*\))?:',
                    r'class \1(BaseAPIClient):',
                    content
                )
                
                # Remove manual session management
                content = re.sub(
                    r'self\._session.*?aiohttp\.ClientSession\(\)',
                    '# Session managed by BaseAPIClient',
                    content,
                    flags=re.DOTALL
                )
                
                # Write updated content
                with open(client_file, 'w') as f:
                    f.write(content)
                
                print(f"✅ Updated session management: {client_file.name}")
    
    def fix_redis_bug(self):
        """Fix the Redis client reference bug in AI service."""
        service_path = self.project_root / "Link_Profiler/services/ai_service.py"
        
        if not service_path.exists():
            print(f"AI service not found: {service_path}")
            return
        
        # Create backup
        self._backup_file(service_path)
        
        # Read content
        with open(service_path, 'r') as f:
            content = f.read()
        
        # Fix the Redis client reference bug
        content = re.sub(
            r'await self\.redis\.close\(\)',
            'await self.redis_client.close()',
            content
        )
        
        # Write updated content
        with open(service_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Fixed Redis client bug: {service_path}")
    
    def _backup_file(self, file_path: Path):
        """Create a backup of a file before modification."""
        backup_path = self.backup_dir / f"{file_path.name}.backup"
        shutil.copy2(file_path, backup_path)
        print(f"📁 Backed up: {file_path.name} -> {backup_path}")
    
    def create_env_example(self):
        """Create .env.example file with all required variables."""
        env_example_content = '''# Link Profiler Environment Variables
# Copy this file to .env and fill in your actual values

# Database Configuration
LP_DATABASE_URL=postgresql://user:password@localhost:5432/link_profiler_db

# Redis Configuration  
LP_REDIS_URL=redis://localhost:6379/0
# LP_REDIS_PASSWORD=your_redis_password_here # Only needed if Redis requires password

# Security
LP_AUTH_SECRET_KEY=your_secret_key_minimum_32_characters_here

# Monitoring
LP_MONITOR_PASSWORD=your_monitor_password_here

# External API Keys
LP_AI_OPENROUTER_API_KEY=your_openrouter_api_key
LP_GOOGLE_API_KEY=your_google_api_key
LP_AHREFS_API_KEY=your_ahrefs_api_key
LP_SEMRUSH_API_KEY=your_semrush_api_key

# Social Media APIs
LP_TWITTER_API_KEY=your_twitter_api_key
LP_TWITTER_API_SECRET=your_twitter_api_secret
LP_TWITTER_BEARER_TOKEN=your_twitter_bearer_token
LP_FACEBOOK_APP_ID=your_facebook_app_id
LP_FACEBOOK_APP_SECRET=your_facebook_app_secret

# Other Services
LP_ETHERSCAN_API_KEY=your_etherscan_api_key
LP_OPENSEA_API_KEY=your_opensea_api_key
LP_NEWS_API_KEY=your_news_api_key

# Optional: Development/Testing
LP_DEBUG=false
LP_LOG_LEVEL=INFO
LP_ENVIRONMENT=production
'''
        
        env_path = self.project_root / ".env.example"
        with open(env_path, 'w') as f:
            f.write(env_example_content)
        
        print(f"✅ Created environment template: {env_path}")

if __name__ == "__main__":
    # This script is intended to be run from the project root
    # For example: python scripts/migrate_placeholders.py
    migrator = PlaceholderMigrator(os.getcwd())
    migrator.create_env_example() # Create the .env.example first
    migrator.migrate_all_placeholders()
