import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Paper, Typography, Box } from '@mui/material'
import { CloudUpload } from '@mui/icons-material'
import axios from 'axios'

export function FileUpload({ onUploadComplete, setIsLoading }) {
  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setIsLoading(true)
    try {
      const response = await axios.post('http://localhost:8000/api/process-payslip', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      onUploadComplete(response.data)
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to process payslip')
    } finally {
      setIsLoading(false)
    }
  }, [onUploadComplete, setIsLoading])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg']
    },
    maxFiles: 1
  })

  return (
    <Paper
      {...getRootProps()}
      sx={{
        p: 6,
        textAlign: 'center',
        cursor: 'pointer',
        bgcolor: isDragActive ? 'action.hover' : 'background.paper',
        border: '2px dashed',
        borderColor: isDragActive ? 'primary.main' : 'grey.300',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          bgcolor: 'action.hover',
          borderColor: 'primary.main',
        }
      }}
    >
      <input {...getInputProps()} />
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
        <CloudUpload sx={{ fontSize: 48, color: 'primary.main' }} />
        <Typography variant="h6" color="text.primary">
          {isDragActive ? 'Drop the payslip here...' : 'Drag and drop your payslip'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          or click to select file
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          Supports PDF, PNG, JPG files
        </Typography>
      </Box>
    </Paper>
  )
} 