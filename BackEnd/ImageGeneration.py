import os
from PIL import Image
import torch
from diffusers import DiffusionPipeline
import random
from groq import Groq
from dotenv import dotenv_values
import psycopg2
from psycopg2.extras import Json
import io
from datetime import datetime

env_vars = dotenv_values(".env")

GroqAPIKeyImage = env_vars.get("GroqAPIKeyImage")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")

groq_client = Groq(api_key=GroqAPIKeyImage)

class LocalImageGenerator:
    def __init__(self):
        self.pipe = None
        self.model_loaded = False
        self._check_gpu()
        
    def _check_gpu(self):
        """Check GPU availability"""
        if not torch.cuda.is_available():
            pass
    
    def _init_db(self):
        """Initialize database and create images table"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS generated_images (
                    id SERIAL PRIMARY KEY,
                    original_prompt TEXT NOT NULL,
                    enhanced_prompt TEXT NOT NULL,
                    image_data BYTEA NOT NULL,
                    seed INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_images_created_at ON generated_images(created_at);
                CREATE INDEX IF NOT EXISTS idx_images_seed ON generated_images(seed);
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            pass
    
    def _truncate_to_word_limit(self, text: str, word_limit: int = 60) -> str:
        """Truncate text to specified word limit"""
        words = text.split()
        if len(words) <= word_limit:
            return text
        return ' '.join(words[:word_limit])
    
    def enhance_prompt_with_groq(self, user_prompt: str) -> str:
        """Use Groq to enhance the user's prompt for better image generation"""
        try:
            
            system_prompt = """You are an expert at creating detailed, high-quality image generation prompts for Stable Diffusion.

Your task: Transform the user's simple prompt into a detailed, descriptive prompt that will generate a stunning, high-quality image.

Guidelines:
- Add specific artistic details (lighting, composition, style, mood)
- Include quality enhancers (highly detailed, 8k, professional, masterpiece)
- Specify camera angles, colors, textures when relevant
- IMPORTANT: Keep it under 60 words total
- Focus on visual elements only
- Don't add negative prompts or technical parameters
                    
Example transformations:
User: "a cat"
Enhanced: "A majestic fluffy cat with bright green eyes, sitting gracefully on a velvet cushion, soft natural lighting, highly detailed fur texture, professional pet photography, 8k quality, shallow depth of field"

User: "sunset beach"
Enhanced: "A breathtaking sunset over a pristine tropical beach, golden hour lighting, vibrant orange and purple sky reflecting on calm ocean waves, palm trees silhouetted against the horizon, ultra realistic, highly detailed, professional landscape photography, 8k resolution"

Now enhance the user's prompt. Remember: Maximum 60 words."""

            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Enhance this image prompt: {user_prompt}"}
                ],
                max_tokens=256,
                temperature=0.7,
                top_p=0.9
            )
            
            enhanced_prompt = completion.choices[0].message.content.strip()
            enhanced_prompt = self._truncate_to_word_limit(enhanced_prompt, 60)
            
            return enhanced_prompt
            
        except Exception as e:
            return self._truncate_to_word_limit(user_prompt, 60)
        
    def load_model(self):
        """Load the Stable Diffusion model (only once) - OPTIMIZED FOR RTX 4060 Mobile"""
        if self.model_loaded:
            return
             
        if not torch.cuda.is_available():
            device = "cpu"
        else:
            device = "cuda"
        
        model_id = "stabilityai/stable-diffusion-xl-base-1.0" 
        
        self.pipe = DiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            variant="fp16" if device == "cuda" else None,
            use_safetensors=True
        )
        
        self.pipe = self.pipe.to(device)

        if device == "cuda" and torch.cuda.get_device_capability()[0] >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        
        self.model_loaded = True

    def generate_image(self, original_prompt: str, seed: int = None):
        """Generate a single high-quality image with AI-enhanced prompt"""
        import time
        timings = {}
        total_start = time.time()
        
        # Step 1: Model loading
        load_start = time.time()
        if not self.model_loaded:
            self.load_model()
        timings['model_load'] = time.time() - load_start
        
        # Step 2: Prompt enhancement
        enhance_start = time.time()
        enhanced_prompt = self.enhance_prompt_with_groq(original_prompt)
        timings['prompt_enhance'] = time.time() - enhance_start
        
        if seed is None:
            seed = random.randint(0, 1000000)
        
        generator = torch.Generator(device=self.pipe.device).manual_seed(seed)
        
        negative_prompt = "blurry, low quality, distorted, deformed, ugly, bad anatomy, bad proportions, watermark, signature, text, low res, pixelated, grainy, artifacts, amateur"
        
        # Step 3: Actual image generation
        gen_start = time.time()
        
        self.pipe.set_progress_bar_config(disable=True)
        image = self.pipe(
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=35,  
            guidance_scale=7.5, 
            generator=generator,
            height=768,  
            width=768    
        ).images[0]
        
        timings['image_generation'] = time.time() - gen_start
        
        timings['total'] = time.time() - total_start
        
        return image, seed, enhanced_prompt

    def save_image_to_db(self, image: Image.Image, original_prompt: str, 
                         enhanced_prompt: str, seed: int):
        """Save generated image to PostgreSQL database"""
        try:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG', quality=95, optimize=True)
            img_byte_arr = img_byte_arr.getvalue()
            
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
            cur = conn.cursor()
            
            metadata = {
                "model": "stabilityai/stable-diffusion-xl-base-1.0",
                "inference_steps": 35,
                "guidance_scale": 7.5,
                "generated_at": datetime.now().isoformat()
            }
            
            cur.execute(
                """INSERT INTO generated_images 
                   (original_prompt, enhanced_prompt, image_data, seed, width, height, metadata) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (original_prompt, enhanced_prompt, psycopg2.Binary(img_byte_arr), 
                 seed, 768, 768, Json(metadata))
            )
            
            image_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            
            return image_id
            
        except Exception as e:
            print(f" Error saving image to database: {e}")
            return None

    def save_image_to_file(self, image: Image.Image, original_prompt: str, seed: int):
        """Save image to local file system as backup"""
        folder_path = "Data"
        os.makedirs(folder_path, exist_ok=True)
        
        prompt_clean = original_prompt.replace(" ", "_")[:50]
        image_path = os.path.join(folder_path, f"{prompt_clean}_{seed}.png")
        
        image.save(image_path, quality=95, optimize=True)
        
        return image_path

    def retrieve_recent_images(self, limit=5):
        """Retrieve recent images from database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT id, original_prompt, enhanced_prompt, seed, created_at 
                   FROM generated_images 
                   ORDER BY created_at DESC 
                   LIMIT %s""",
                (limit,)
            )
            
            images = cur.fetchall()
            conn.close()
            
            return images
            
        except Exception as e:
            print(f"Error retrieving images: {e}")
            return []

    def delete_image_history(self, confirm=True):
        """Delete all images from database"""
        try:
            if confirm:
                response = input("\n  Delete ALL image history? This cannot be undone! (yes/no): ").strip().lower()
                if response != 'yes':
                    print("Deletion cancelled.")
                    return False
            
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM generated_images")
            count = cur.fetchone()[0]
            
            cur.execute("DELETE FROM generated_images")
            conn.commit()
            conn.close()
            
            print(f" Deleted {count} image(s) from database")
            return True
            
        except Exception as e:
            print(f" Error deleting images: {e}")
            return False

    def delete_specific_image(self, image_id):
        """Delete a specific image by ID"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("DELETE FROM generated_images WHERE id = %s", (image_id,))
            rows_deleted = cur.rowcount
            conn.commit()
            conn.close()
            
            if rows_deleted > 0:
                print(f" Deleted image ID {image_id}")
                return True
            else:
                print(f" Image ID {image_id} not found")
                return False
            
        except Exception as e:
            print(f" Error deleting image: {e}")
            return False