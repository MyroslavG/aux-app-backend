-- Create storage buckets for images
INSERT INTO storage.buckets (id, name, public)
VALUES
    ('user-images', 'user-images', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for user-images bucket
CREATE POLICY "Anyone can view images"
ON storage.objects FOR SELECT
USING (bucket_id = 'user-images');

CREATE POLICY "Users can upload their own images"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'user-images'
    AND auth.role() = 'authenticated'
);

CREATE POLICY "Users can update their own images"
ON storage.objects FOR UPDATE
USING (
    bucket_id = 'user-images'
    AND auth.uid()::text = (storage.foldername(name))[1]
);

CREATE POLICY "Users can delete their own images"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'user-images'
    AND auth.uid()::text = (storage.foldername(name))[1]
);
