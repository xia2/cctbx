#include <sys/time.h>
#include "diffBraggCUDA.h"
#include "diffBragg_gpu_kernel.h"

#define BLOCKSIZE 256
#define NUMBLOCKS 256

void diffBragg_loopy(
        int Npix_to_model, std::vector<unsigned int>& panels_fasts_slows,
        image_type& floatimage,
        image_type& d_Umat_images, image_type& d2_Umat_images,
        image_type& d_Bmat_images, image_type& d2_Bmat_images,
        image_type& d_Ncells_images, image_type& d2_Ncells_images,
        image_type& d_fcell_images, image_type& d2_fcell_images,
        image_type& d_eta_images,
        image_type& d_lambda_images, image_type& d2_lambda_images,
        image_type& d_panel_rot_images, image_type& d2_panel_rot_images,
        image_type& d_panel_orig_images, image_type& d2_panel_orig_images,
        int* subS_pos, int* subF_pos, int* thick_pos,
        int* source_pos, int* phi_pos, int* mos_pos,
        const int Nsteps, int _printout_fpixel, int _printout_spixel, bool _printout, CUDAREAL _default_F,
        int oversample, bool _oversample_omega, CUDAREAL subpixel_size, CUDAREAL pixel_size,
        CUDAREAL detector_thickstep, CUDAREAL _detector_thick, CUDAREAL close_distance, CUDAREAL detector_attnlen,
        bool use_lambda_coefficients, CUDAREAL lambda0, CUDAREAL lambda1,
        MAT3& eig_U, MAT3& eig_O, MAT3& eig_B, MAT3& RXYZ,
        std::vector<VEC3,Eigen::aligned_allocator<VEC3> >& dF_vecs,
        std::vector<VEC3,Eigen::aligned_allocator<VEC3> >& dS_vecs,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& UMATS_RXYZ,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& UMATS_RXYZ_prime,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& RotMats,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& dRotMats,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& d2RotMats,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& UMATS,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& dB_Mats,
        std::vector<MAT3,Eigen::aligned_allocator<MAT3> >& dB2_Mats,
        CUDAREAL* source_X, CUDAREAL* source_Y, CUDAREAL* source_Z, CUDAREAL* source_lambda, CUDAREAL* source_I,
        CUDAREAL kahn_factor,
        CUDAREAL Na, CUDAREAL Nb, CUDAREAL Nc,
        CUDAREAL phi0, CUDAREAL phistep,
        VEC3& spindle_vec, VEC3 _polarization_axis,
        int h_range, int k_range, int l_range,
        int h_max, int h_min, int k_max, int k_min, int l_max, int l_min, CUDAREAL dmin,
        CUDAREAL fudge, bool complex_miller, int verbose, bool only_save_omega_kahn,
        bool isotropic_ncells, bool compute_curvatures,
        std::vector<CUDAREAL>& _FhklLinear, std::vector<CUDAREAL>& _Fhkl2Linear,
        std::vector<bool>& refine_Bmat, std::vector<bool>& refine_Ncells, std::vector<bool>& refine_panel_origin, std::vector<bool>& refine_panel_rot,
        bool refine_fcell, std::vector<bool>& refine_lambda, bool refine_eta, std::vector<bool>& refine_Umat,
        std::vector<CUDAREAL>& fdet_vectors, std::vector<CUDAREAL>& sdet_vectors,
        std::vector<CUDAREAL>& odet_vectors, std::vector<CUDAREAL>& pix0_vectors,
        bool _nopolar, bool _point_pixel, CUDAREAL _fluence, CUDAREAL _r_e_sqr, CUDAREAL _spot_scale,
        int number_of_sources, int device_Id,
        diffBragg_cudaPointers& cp,
        bool update_step_positions, bool update_panels_fasts_slows, bool update_sources, bool update_umats,
        bool update_dB_mats, bool update_rotmats, bool update_Fhkl, bool update_detector, bool update_refine_flags ,
        bool update_panel_deriv_vecs){ // diffBragg cuda loopy

    bool ALLOC = !cp.device_is_allocated;


    double time;
    struct timeval t1, t2, t3 ,t4;
    gettimeofday(&t1, 0);


//  BEGIN step position
    if (ALLOC){
        cudaMallocManaged(&cp.cu_subS_pos, Nsteps*sizeof(int));
        cudaMallocManaged(&cp.cu_subF_pos, Nsteps*sizeof(int));
        cudaMallocManaged(&cp.cu_thick_pos, Nsteps*sizeof(int));
        cudaMallocManaged(&cp.cu_source_pos, Nsteps*sizeof(int));
        cudaMallocManaged(&cp.cu_mos_pos, Nsteps*sizeof(int));
        cudaMallocManaged(&cp.cu_phi_pos, Nsteps*sizeof(int));
        
        cudaMallocManaged(&cp.cu_source_X, number_of_sources*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_source_Y, number_of_sources*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_source_Z, number_of_sources*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_source_I, number_of_sources*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_source_lambda, number_of_sources*sizeof(CUDAREAL));
        
        
        cudaMallocManaged((void **)&cp.cu_UMATS, UMATS.size()*sizeof(MAT3));
        cudaMallocManaged((void **)&cp.cu_UMATS_RXYZ, UMATS_RXYZ.size()*sizeof(MAT3));
        cudaMallocManaged((void **)&cp.cu_UMATS_RXYZ_prime, UMATS_RXYZ_prime.size()*sizeof(MAT3));
        
        cudaMallocManaged((void **)&cp.cu_dB_Mats, dB_Mats.size()*sizeof(MAT3));
        cudaMallocManaged((void **)&cp.cu_dB2_Mats, dB2_Mats.size()*sizeof(MAT3));
        
        cudaMallocManaged((void **)&cp.cu_RotMats, RotMats.size()*sizeof(MAT3));
        cudaMallocManaged((void **)&cp.cu_dRotMats, dRotMats.size()*sizeof(MAT3));
        cudaMallocManaged((void **)&cp.cu_d2RotMats, d2RotMats.size()*sizeof(MAT3));
        
        cudaMallocManaged(&cp.cu_fdet_vectors, fdet_vectors.size()*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_sdet_vectors, fdet_vectors.size()*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_odet_vectors, fdet_vectors.size()*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_pix0_vectors, fdet_vectors.size()*sizeof(CUDAREAL));
        
        cudaMallocManaged(&cp.cu_refine_Bmat, 6*sizeof(bool));
        cudaMallocManaged(&cp.cu_refine_Umat, 3*sizeof(bool));
        cudaMallocManaged(&cp.cu_refine_Ncells, 3*sizeof(bool));
        cudaMallocManaged(&cp.cu_refine_panel_origin, 3*sizeof(bool));
        cudaMallocManaged(&cp.cu_refine_panel_rot, 3*sizeof(bool));
        cudaMallocManaged(&cp.cu_refine_lambda, 2*sizeof(bool));
        
        cudaMallocManaged(&cp.cu_Fhkl, _FhklLinear.size()*sizeof(CUDAREAL));
        if (complex_miller)
            cudaMallocManaged(&cp.cu_Fhkl2, _FhklLinear.size()*sizeof(CUDAREAL));
        
        cudaMallocManaged((void **)&cp.cu_dF_vecs, dF_vecs.size()*sizeof(VEC3));
        cudaMallocManaged((void **)&cp.cu_dS_vecs, dF_vecs.size()*sizeof(VEC3));
        
    
        //gettimeofday(&t3, 0);
        cudaMallocManaged(&cp.cu_floatimage, Npix_to_model*sizeof(CUDAREAL) );
        cudaMallocManaged(&cp.cu_d_fcell_images, Npix_to_model*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_eta_images, Npix_to_model*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_Umat_images, Npix_to_model*3*sizeof(CUDAREAL) );
        cudaMallocManaged(&cp.cu_d_Ncells_images, Npix_to_model*3*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_panel_rot_images, Npix_to_model*3*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_panel_orig_images, Npix_to_model*3*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_lambda_images, Npix_to_model*2*sizeof(CUDAREAL));
        cudaMallocManaged(&cp.cu_d_Bmat_images, Npix_to_model*6*sizeof(CUDAREAL));
        //gettimeofday(&t4, 0);
        //time = (1000000.0*(t4.tv_sec-t3.tv_sec) + t4.tv_usec-t3.tv_usec)/1000.0;
        //printf("TIME SPENT ALLOCATING (IMAGES ONLY):  %3.10f ms \n", time);
        
        cudaMallocManaged(&cp.cu_panels_fasts_slows, panels_fasts_slows.size()*sizeof(panels_fasts_slows[0]));
    } // END ALLOC
    
    gettimeofday(&t2, 0);
    time = (1000000.0*(t2.tv_sec-t1.tv_sec) + t2.tv_usec-t1.tv_usec)/1000.0;
    if(verbose>1)
        printf("TIME SPENT ALLOCATING (TOTAL):  %3.10f ms \n", time);


//  BEGIN COPYING DATA
    gettimeofday(&t1, 0);

    if (update_step_positions || ALLOC){
        for(int i=0; i< Nsteps;i++){
            cp.cu_subS_pos[i] = subS_pos[i];
            cp.cu_subF_pos[i] = subF_pos[i];
            cp.cu_thick_pos[i] = thick_pos[i];
            cp.cu_mos_pos[i] = mos_pos[i];
            cp.cu_phi_pos[i] = phi_pos[i];
            cp.cu_source_pos[i] = source_pos[i];
        }
        cudaDeviceSynchronize();
    }
//  END step position
    int kaladin_stormblessed = 777;


//  BEGIN sources
    if (update_sources || ALLOC){
        for (int i=0; i< number_of_sources; i++){
            cp.cu_source_X[i] = source_X[i];
            cp.cu_source_Y[i] = source_Y[i];
            cp.cu_source_Z[i] = source_Z[i];
            cp.cu_source_I[i] = source_I[i];
            cp.cu_source_lambda[i] = source_lambda[i];
        }
    }
//  END sources


//  UMATS
    if (update_umats || ALLOC){
        for (int i=0; i< UMATS.size(); i++)
            cp.cu_UMATS[i] = UMATS[i];
        for (int i=0; i < UMATS_RXYZ.size(); i++)
            cp.cu_UMATS_RXYZ[i] = UMATS_RXYZ[i];
        for (int i=0; i < UMATS_RXYZ_prime.size(); i++)
            cp.cu_UMATS_RXYZ_prime[i] = UMATS_RXYZ_prime[i];
        cudaDeviceSynchronize();
    }
//  END UMATS




//  BMATS
    if(update_dB_mats || ALLOC){
        for (int i=0; i< dB_Mats.size(); i++)
            cp.cu_dB_Mats[i] = dB_Mats[i];
        for (int i=0; i< dB2_Mats.size(); i++)
            cp.cu_dB2_Mats[i] = dB2_Mats[i];
        cudaDeviceSynchronize();
    }
//  END BMATS



//  ROT MATS
    if(update_rotmats || ALLOC){
        for (int i=0; i<RotMats.size(); i++)
            cp.cu_RotMats[i] = RotMats[i];
        for (int i=0; i<dRotMats.size(); i++)
            cp.cu_dRotMats[i] = dRotMats[i];
        for (int i=0; i<d2RotMats.size(); i++)
            cp.cu_d2RotMats[i] = d2RotMats[i];
        cudaDeviceSynchronize();
    }
//  END ROT MATS



//  DETECTOR VECTORS
    if (update_detector || ALLOC){
        for (int i=0; i<fdet_vectors.size(); i++){
            cp.cu_fdet_vectors[i] = fdet_vectors[i];
            cp.cu_sdet_vectors[i] = sdet_vectors[i];
            cp.cu_odet_vectors[i] = odet_vectors[i];
            cp.cu_pix0_vectors[i] = pix0_vectors[i];
        }
    }
//  END  DETECTOR VECTORS



//  BEGIN REFINEMENT FLAGS
    if (update_refine_flags || ALLOC){
        for (int i=0; i<3; i++){
            cp.cu_refine_Umat[i] = refine_Umat[i];
            cp.cu_refine_Ncells[i] = refine_Ncells[i];
            cp.cu_refine_panel_origin[i] = refine_panel_origin[i];
            cp.cu_refine_panel_rot[i] = refine_panel_rot[i];
        }
        for(int i=0; i<2; i++)
            cp.cu_refine_lambda[i] = refine_lambda[i];
        for(int i=0; i<6; i++)
            cp.cu_refine_Bmat[i] = refine_Bmat[i];
    }
//  END REFINEMENT FLAGS

//  BEGIN Fhkl
    if (update_Fhkl || ALLOC){
        for(int i=0; i < _FhklLinear.size(); i++){
          cp.cu_Fhkl[i] = _FhklLinear[i];
          if (complex_miller)
              cp.cu_Fhkl2[i] = _Fhkl2Linear[i];
        }
    }
// END Fhkl

//  BEGIN panel derivative vecs
    if(update_panel_deriv_vecs || ALLOC){
        for (int i=0; i<dF_vecs.size(); i++){
            cp.cu_dF_vecs[i] = dF_vecs[i];
            cp.cu_dS_vecs[i] = dS_vecs[i];
        }
    }
//  END panel derivative vecs


//  BEGIN IMAGES
    //for (int i = 0; i < N; i++){
    //    cp.cu_floatimage[i] = floatimage[i];
    //    cp.cu_d_fcell_images[i] = d_fcell_images[i];
    //    cp.cu_d_eta_images[i] = d_eta_images[i];
    //}
    //for(int i=0; i<3*N; i++){
    //    cp.cu_d_Umat_images[i] = d_Umat_images[i];
    //    cp.cu_d_Ncells_images[i] = d_Ncells_images[i];
    //    cp.cu_d_panel_rot_images[i] = d_panel_rot_images[i];
    //    cp.cu_d_panel_orig_images[i] = d_panel_orig_images[i];
    //}
    //for(int i=0; i<2*N; i++)
    //    cp.cu_d_lambda_images[i] = d_lambda_images[i];
    //for(int i=0; i<6*N;i++)
    //    cp.cu_d_Bmat_images[i] = d_Bmat_images[i];
//  END IMAGES




//  BEGIN panels fasts slows
    if (update_panels_fasts_slows || ALLOC){
        for (int i=0; i< panels_fasts_slows.size(); i++)
            cp.cu_panels_fasts_slows[i] = panels_fasts_slows[i];
    }
//  END panels fasts slows


    gettimeofday(&t2, 0);
    time = (1000000.0*(t2.tv_sec-t1.tv_sec) + t2.tv_usec-t1.tv_usec)/1000.0;
    if(verbose>1)
        printf("TIME SPENT COPYING DATA HOST->DEV:  %3.10f ms \n", time);


    cp.device_is_allocated = true;


    gettimeofday(&t1, 0);
    gpu_sum_over_steps<<<NUMBLOCKS, BLOCKSIZE>>>(
        Npix_to_model, cp.cu_panels_fasts_slows,
        cp.cu_floatimage,
        cp.cu_d_Umat_images, cp.cu_d2_Umat_images,
        cp.cu_d_Bmat_images, cp.cu_d2_Bmat_images,
        cp.cu_d_Ncells_images, cp.cu_d2_Ncells_images,
        cp.cu_d_fcell_images, cp.cu_d2_fcell_images,
        cp.cu_d_eta_images,
        cp.cu_d_lambda_images, cp.cu_d2_lambda_images,
        cp.cu_d_panel_rot_images, cp.cu_d2_panel_rot_images,
        cp.cu_d_panel_orig_images, cp.cu_d2_panel_orig_images,
        cp.cu_subS_pos, cp.cu_subF_pos, cp.cu_thick_pos,
        cp.cu_source_pos, cp.cu_phi_pos, cp.cu_mos_pos,
        Nsteps, _printout_fpixel, _printout_spixel, _printout, _default_F,
        oversample,  _oversample_omega, subpixel_size, pixel_size,
        detector_thickstep, _detector_thick, close_distance, detector_attnlen,
        use_lambda_coefficients, lambda0, lambda1,
        eig_U, eig_O, eig_B, RXYZ,
        cp.cu_dF_vecs,
        cp.cu_dS_vecs,
        cp.cu_UMATS_RXYZ,
        cp.cu_UMATS_RXYZ_prime,
        cp.cu_RotMats,
        cp.cu_dRotMats,
        cp.cu_d2RotMats,
        cp.cu_UMATS,
        cp.cu_dB_Mats,
        cp.cu_dB2_Mats,
        cp.cu_source_X, cp.cu_source_Y, cp.cu_source_Z, cp.cu_source_lambda, cp.cu_source_I,
        kahn_factor,
        Na, Nb, Nc,
        phi0, phistep,
        spindle_vec, _polarization_axis,
        h_range, k_range, l_range,
        h_max, h_min, k_max, k_min, l_max, l_min, dmin,
        fudge, complex_miller, verbose, only_save_omega_kahn,
        isotropic_ncells, compute_curvatures,
        cp.cu_Fhkl, cp.cu_Fhkl2,
        cp.cu_refine_Bmat, cp.cu_refine_Ncells, cp.cu_refine_panel_origin, cp.cu_refine_panel_rot,
        refine_fcell, cp.cu_refine_lambda, refine_eta, cp.cu_refine_Umat,
        cp.cu_fdet_vectors, cp.cu_sdet_vectors,
        cp.cu_odet_vectors, cp.cu_pix0_vectors,
        _nopolar, _point_pixel, _fluence, _r_e_sqr, _spot_scale);

    cudaDeviceSynchronize();
    if(verbose>1)
        printf("KERNEL_COMPLETE gpu_sum_over_steps\n");
    gettimeofday(&t2, 0);
    time = (1000000.0*(t2.tv_sec-t1.tv_sec) + t2.tv_usec-t1.tv_usec)/1000.0;
    if(verbose>1)
        printf("TIME SPENT(KERNEL):  %3.10f ms \n", time);

    gettimeofday(&t1, 0);
//  COPY BACK FROM DEVICE
    for (int i=0; i< Npix_to_model; i++){
        if (i==0)
            printf("A value: %f, floatimage: %f\n", cp.cu_floatimage[i], floatimage[i]);
        floatimage[i] = cp.cu_floatimage[i];
        d_eta_images[i] = cp.cu_d_eta_images[i];
        d_fcell_images[i] = cp.cu_d_fcell_images[i];
    }
    for (int i=0; i<3*Npix_to_model; i++){
        d_Umat_images[i] = cp.cu_d_Umat_images[i];
        d_panel_rot_images[i] = cp.cu_d_panel_rot_images[i];
        d_panel_orig_images[i] = cp.cu_d_panel_orig_images[i];
        d_Ncells_images[i] = cp.cu_d_Ncells_images[i];
    }

    for(int i=0; i<6*Npix_to_model; i++)
        d_Bmat_images[i] = cp.cu_d_Bmat_images[i];
    for(int i=0; i<2*Npix_to_model; i++)
        d_lambda_images[i] = cp.cu_d_lambda_images[i];

    //printf("COPY images device->host\n");
    
    gettimeofday(&t2, 0);
    time = (1000000.0*(t2.tv_sec-t1.tv_sec) + t2.tv_usec-t1.tv_usec)/1000.0;
    if(verbose>1)
        printf("TIME SPENT COPYING BACK :  %3.10f ms \n", time);

}


void freedom(diffBragg_cudaPointers& cp){

    cudaFree( cp.cu_floatimage);
    cudaFree( cp.cu_d_Umat_images);
    cudaFree( cp.cu_d_Bmat_images);
    cudaFree( cp.cu_d_Ncells_images);
    cudaFree( cp.cu_d_eta_images);
    cudaFree( cp.cu_d_fcell_images);
    cudaFree( cp.cu_d_lambda_images);
    cudaFree( cp.cu_d_panel_rot_images);
    cudaFree( cp.cu_d_panel_orig_images);

    cudaFree( cp.cu_subS_pos);
    cudaFree( cp.cu_subF_pos);
    cudaFree( cp.cu_thick_pos);
    cudaFree( cp.cu_mos_pos);
    cudaFree( cp.cu_phi_pos);
    cudaFree( cp.cu_source_pos);

    cudaFree(cp.cu_Fhkl);
    cudaFree(cp.cu_Fhkl2);

    cudaFree(cp.cu_fdet_vectors);
    cudaFree(cp.cu_sdet_vectors);
    cudaFree(cp.cu_odet_vectors);
    cudaFree(cp.cu_pix0_vectors);

    cudaFree(cp.cu_source_X);
    cudaFree(cp.cu_source_Y);
    cudaFree(cp.cu_source_Z);
    cudaFree(cp.cu_source_I);
    cudaFree(cp.cu_source_lambda);

    cudaFree(cp.cu_UMATS);
    cudaFree(cp.cu_UMATS_RXYZ);
    cudaFree(cp.cu_UMATS_RXYZ_prime);
    cudaFree(cp.cu_RotMats);
    cudaFree(cp.cu_dRotMats);
    cudaFree(cp.cu_d2RotMats);
    cudaFree(cp.cu_dB_Mats);
    cudaFree(cp.cu_dB2_Mats);

    cudaFree(cp.cu_dF_vecs);
    cudaFree(cp.cu_dS_vecs);

    cudaFree(cp.cu_refine_Bmat);
    cudaFree(cp.cu_refine_Umat);
    cudaFree(cp.cu_refine_Ncells);
    cudaFree(cp.cu_refine_lambda);
    cudaFree(cp.cu_refine_panel_origin);
    cudaFree(cp.cu_refine_panel_rot);

    cudaFree(cp.cu_panels_fasts_slows);

    cp.device_is_allocated = false;
}



// Kernel function to add the elements of two arrays
__global__
void phat_add(int n, float *x, float *y)
{
  for (int i = 0; i < n; i++)
    y[i] = x[i] + y[i];
}

int phat_main(void)
{
  int N = 1<<20;
  float *x, *y;

  // Allocate Unified Memory  accessible from CPU or GPU
  cudaMallocManaged(&x, N*sizeof(float));
  cudaMallocManaged(&y, N*sizeof(float));

  // initialize x and y arrays on the host
  for (int i = 0; i < N; i++) {
    x[i] = 1.0f;
    y[i] = 2.0f;
  }

  // Run kernel on 1M elements on the GPU
  phat_add<<<1, 1>>>(N, x, y);

  // Wait for GPU to finish before accessing on host
  cudaDeviceSynchronize();

  // Check for errors (all values should be 3.0f)
  float maxError = 0.0f;
  for (int i = 0; i < N; i++)
    maxError = fmax(maxError, fabs(y[i]-3.0f));
  std::cout << "Max error: " << maxError << std::endl;

  // Free memory
  cudaFree(x);
  cudaFree(y);

  return 0;
}







